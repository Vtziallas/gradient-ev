# Gradient — Database Design (PostgreSQL 16 + PostGIS 3.4)

Conventions: `uuid` PKs — UUIDv7 for index locality, generated app-side (`uuid_generate_v7()`
below denotes the app/SQLAlchemy default, not a Postgres built-in), `timestamptz` everywhere, soft deletes only
where GDPR requires audit (`deleted_at`), `geography(…,4326)` for all geo columns, one
Alembic migration chain. Module ownership is enforced socially + by schema comments; all
tables in schema `public` for MVP (schema-per-module adds friction before it adds value).

## 1. Identity & users

```sql
CREATE TABLE users (
  id              uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  email           citext UNIQUE NOT NULL,
  display_name    text NOT NULL,
  locale          text NOT NULL DEFAULT 'en',
  unit_system     text NOT NULL DEFAULT 'metric' CHECK (unit_system IN ('metric','imperial')),
  soc_reserve_pct smallint NOT NULL DEFAULT 10,
  marketing_opt_in boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz            -- GDPR erasure marker; PII nulled on erasure
);

CREATE TABLE auth_identities (           -- password or OAuth providers
  id            uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider      text NOT NULL CHECK (provider IN ('password','apple','google')),
  provider_uid  text,                    -- sub claim for OAuth
  password_hash text,                    -- argon2id; NULL for OAuth
  UNIQUE (provider, provider_uid)
);

CREATE TABLE refresh_tokens (
  id          uuid PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  family_id   uuid NOT NULL,             -- rotation family; reuse detection revokes family
  token_hash  bytea NOT NULL,
  expires_at  timestamptz NOT NULL,
  revoked_at  timestamptz,
  device_info jsonb
);
```

## 2. Vehicles

```sql
CREATE TABLE vehicle_models (            -- curated catalog, versioned releases
  id                uuid PRIMARY KEY,
  make              text NOT NULL, model text NOT NULL, variant text NOT NULL,
  year_from         smallint, year_to smallint,
  mass_kg           numeric(6,1) NOT NULL,
  cd                numeric(4,3) NOT NULL,
  frontal_area_m2   numeric(4,2) NOT NULL,
  c_rr_base         numeric(5,4) NOT NULL DEFAULT 0.010,
  usable_kwh        numeric(5,1) NOT NULL,
  max_regen_kw      numeric(5,1) NOT NULL,
  max_dc_kw         numeric(5,1) NOT NULL,
  max_ac_kw         numeric(4,1) NOT NULL,
  charge_curve      jsonb NOT NULL,      -- [{soc, kw}]
  drivetrain_eff    numeric(3,2) NOT NULL DEFAULT 0.90,
  regen_eff         numeric(3,2) NOT NULL DEFAULT 0.65,
  aux_base_w        integer NOT NULL DEFAULT 350,
  has_heat_pump     boolean NOT NULL DEFAULT true,
  connectors        text[] NOT NULL,     -- {'ccs2','type2',...}
  epa_range_km      numeric(5,0),
  data_quality      smallint NOT NULL DEFAULT 1,  -- 1 rough … 5 validated
  catalog_version   integer NOT NULL,
  UNIQUE (make, model, variant, year_from)
);

CREATE TABLE vehicles (                  -- a user's car
  id                 uuid PRIMARY KEY DEFAULT uuid_generate_v7(),
  user_id            uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vehicle_model_id   uuid NOT NULL REFERENCES vehicle_models(id),
  nickname           text,
  degradation_factor numeric(3,2) NOT NULL DEFAULT 1.00,  -- 0.85 = 15% degraded
  calibration_factor numeric(4,3) NOT NULL DEFAULT 1.000, -- learned, per §EnergyEngine
  tire_pressure_ok   boolean NOT NULL DEFAULT true,
  odometer_km        integer,
  is_default         boolean NOT NULL DEFAULT false,
  created_at         timestamptz NOT NULL DEFAULT now()
);
```

## 3. Routes & elevation

```sql
CREATE TABLE routes (                    -- a planned route bundle (cacheable artifact)
  id              uuid PRIMARY KEY,
  user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
  request_hash    text NOT NULL,         -- dedupe key (see Architecture §8)
  origin          geography(Point,4326) NOT NULL,
  destination     geography(Point,4326) NOT NULL,
  geometry        geography(LineString,4326) NOT NULL,
  distance_m      integer NOT NULL,
  duration_s      integer NOT NULL,
  ascent_m        integer NOT NULL, descent_m integer NOT NULL,
  engine_version  text NOT NULL, catalog_version integer NOT NULL,
  vehicle_model_id uuid NOT NULL REFERENCES vehicle_models(id),
  context         jsonb NOT NULL,        -- TripContext snapshot (passengers, hvac…)
  prediction      jsonb NOT NULL,        -- arrival soc, best/worst, confidence
  energy_timeline jsonb NOT NULL,        -- chapters (see EnergyEngine §7)
  charging_plan   jsonb,                 -- stops array
  samples_ref     text,                  -- S3 key of full 25m sample array (parquet)
  created_at      timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz NOT NULL   -- weather-dependent → hours, not days
);
CREATE INDEX routes_hash_idx ON routes (request_hash, created_at DESC);
CREATE INDEX routes_geom_idx ON routes USING GIST (geometry);

CREATE TABLE elevation_tiles (           -- decoded DEM cache (L3)
  z smallint NOT NULL, x integer NOT NULL, y integer NOT NULL,
  source        text NOT NULL,           -- 'mapbox-dem-v1' | 'google'
  heights       bytea NOT NULL,          -- 256x256 int16 decimeters, zstd
  fetched_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (z, x, y, source)
);
```

Full per-sample arrays live in S3 parquet (`samples_ref`), not rows — 10k rows/route would
bloat OLTP for data that is only ever read whole.

## 4. Trips & telemetry

```sql
CREATE TABLE trips (
  id              uuid PRIMARY KEY,
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vehicle_id      uuid NOT NULL REFERENCES vehicles(id),
  route_id        uuid REFERENCES routes(id) ON DELETE SET NULL,
  started_at      timestamptz NOT NULL,
  ended_at        timestamptz,
  start_soc       numeric(4,1), end_soc numeric(4,1),
  distance_m      integer, energy_used_kwh numeric(6,2), energy_regen_kwh numeric(6,2),
  efficiency_score smallint,             -- 0-100, from reports module
  predicted_end_soc numeric(4,1),        -- for accuracy tracking
  engine_version  text,
  summary         jsonb                  -- coach report payload
);

CREATE TABLE trip_samples (              -- 1Hz telemetry, monthly partitions
  trip_id     uuid NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
  ts          timestamptz NOT NULL,
  location    geography(Point,4326) NOT NULL,
  speed_mps   real, heading real, altitude_m real,
  soc_pct     real,                      -- user-entered or telemetry
  power_kw    real,                      -- derived/observed
  route_s_m   integer,                   -- map-matched distance along route
  PRIMARY KEY (trip_id, ts)
) PARTITION BY RANGE (ts);
```

Partitions auto-created monthly by a worker job; partitions older than 13 months are
exported to S3 parquet (ML lake) and dropped.

## 5. Charging

```sql
CREATE TABLE charging_stations (
  id             uuid PRIMARY KEY,
  source         text NOT NULL,          -- 'ocm' | 'ocpi:<operator>' | 'nrel'
  source_id      text NOT NULL,
  name           text NOT NULL,
  operator       text,
  location       geography(Point,4326) NOT NULL,
  address        jsonb,
  amenities      jsonb,                  -- precomputed OSM POIs within 400m
  reliability    numeric(3,2) NOT NULL DEFAULT 0.80, -- blended score, see community
  is_active      boolean NOT NULL DEFAULT true,
  updated_at     timestamptz NOT NULL,
  UNIQUE (source, source_id)
);
CREATE INDEX charging_stations_geo_idx ON charging_stations USING GIST (location);

CREATE TABLE charging_connectors (
  id           uuid PRIMARY KEY,
  station_id   uuid NOT NULL REFERENCES charging_stations(id) ON DELETE CASCADE,
  standard     text NOT NULL,            -- ccs2, chademo, type2, nacs
  max_kw       numeric(5,1) NOT NULL,
  price        jsonb,                    -- {per_kwh, per_min, session_fee, currency}
  status       text NOT NULL DEFAULT 'unknown', -- available|occupied|broken|unknown
  status_at    timestamptz
);

CREATE TABLE charging_sessions (         -- user-recorded or planned-then-confirmed
  id           uuid PRIMARY KEY,
  trip_id      uuid REFERENCES trips(id) ON DELETE CASCADE,
  station_id   uuid REFERENCES charging_stations(id),
  arrival_soc  numeric(4,1), departure_soc numeric(4,1),
  started_at   timestamptz, ended_at timestamptz,
  energy_kwh   numeric(6,2), cost numeric(8,2), currency text,
  planned      jsonb                     -- optimizer's plan, for accuracy tracking
);

CREATE TABLE station_occupancy (         -- hour-of-week wait model input
  station_id  uuid NOT NULL REFERENCES charging_stations(id) ON DELETE CASCADE,
  hour_of_week smallint NOT NULL,        -- 0..167
  samples     integer NOT NULL DEFAULT 0,
  occupied_ratio numeric(3,2),
  PRIMARY KEY (station_id, hour_of_week)
);
```

## 6. Weather & traffic snapshots

```sql
CREATE TABLE weather_cells (             -- gridded forecast cache (~11km cells)
  cell_id     text NOT NULL,             -- geohash5
  forecast_at timestamptz NOT NULL,      -- valid time
  fetched_at  timestamptz NOT NULL,
  data        jsonb NOT NULL,            -- temp, wind u/v, rain, snow, humidity, pressure
  PRIMARY KEY (cell_id, forecast_at)
);

CREATE TABLE traffic_segments (          -- optional persisted snapshots for analytics
  id bigserial PRIMARY KEY,
  geometry geography(LineString,4326) NOT NULL,
  observed_at timestamptz NOT NULL,
  speed_kmh real, freeflow_kmh real
);
```

(Live weather/traffic is served from Redis; these tables exist for analytics/replay.)

## 7. Community, gamification, stats

```sql
CREATE TABLE community_reports (
  id          uuid PRIMARY KEY,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('charger_broken','charger_ok','traffic',
                 'road_closed','dangerous_descent','construction','tip')),
  station_id  uuid REFERENCES charging_stations(id),
  location    geography(Point,4326),
  body        text,
  status      text NOT NULL DEFAULT 'active', -- active|expired|removed
  upvotes     integer NOT NULL DEFAULT 0, downvotes integer NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz
);

CREATE TABLE achievements (
  id    text PRIMARY KEY,                -- 'battery_wizard', 'mountain_expert'…
  name  text NOT NULL, description text NOT NULL, icon text NOT NULL,
  rule  jsonb NOT NULL                   -- declarative criteria, evaluated by worker
);
CREATE TABLE user_achievements (
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  achievement_id text REFERENCES achievements(id),
  earned_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, achievement_id)
);

CREATE TABLE driver_stats (              -- denormalized rollup, updated by worker
  user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  total_trips int NOT NULL DEFAULT 0,
  total_km numeric(10,1) NOT NULL DEFAULT 0,
  total_kwh numeric(10,1) NOT NULL DEFAULT 0,
  total_regen_kwh numeric(10,1) NOT NULL DEFAULT 0,
  avg_efficiency_score numeric(4,1),
  longest_regen_m integer,
  updated_at timestamptz NOT NULL
);

CREATE TABLE leaderboard_entries (       -- weekly, per region + vehicle class
  period      daterange NOT NULL,
  scope       text NOT NULL,             -- 'global' | 'region:GR' | 'model:<uuid>'
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  score       numeric(6,2) NOT NULL,
  rank        integer,
  PRIMARY KEY (period, scope, user_id)
);
```

## 8. Notifications & analytics

```sql
CREATE TABLE notifications (
  id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind text NOT NULL, payload jsonb NOT NULL,
  sent_at timestamptz, read_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE device_tokens (
  user_id uuid REFERENCES users(id) ON DELETE CASCADE,
  platform text NOT NULL, token text NOT NULL, updated_at timestamptz NOT NULL,
  PRIMARY KEY (user_id, token)
);
-- Product analytics events go to S3 via Kinesis Firehose, not Postgres.
```

## 9. Indexing & performance notes

- Every FK gets an index (Postgres doesn't auto-create them).
- `charging_stations`: corridor search = `ST_DWithin(location, :route_buffer, 0)` with GIST;
  buffer precomputed once per plan.
- `trips (user_id, started_at DESC)` for history lists.
- JSONB columns are read-whole artifacts; no GIN indexes until a query needs one.
- Target: all OLTP queries < 20 ms p95; anything slower moves to a worker or S3/Athena.

## 10. Data retention (GDPR)

| Data | Retention | Erasure behavior |
|---|---|---|
| Account/PII | life of account | hard-nulled on erasure request (30-day grace) |
| trip_samples | 13 months hot, then anonymized parquet | user_id dropped in lake export |
| routes | expires_at (≤48 h) then deleted | n/a |
| community_reports | 12 months | authorship anonymized |
