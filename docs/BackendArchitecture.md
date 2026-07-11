# Gradient — Backend Architecture (FastAPI)

## 1. Stack

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 async + GeoAlchemy2, Alembic, asyncpg,
redis-py, arq (jobs), httpx (outbound), NumPy/SciPy (engine), uv (deps), ruff + mypy strict.

## 2. Repository layout

```
backend/
├── pyproject.toml
├── alembic/                      # single migration chain
├── gradient_energy/              # PURE physics package — no I/O, no FastAPI imports
│   ├── model.py                  # forces, power, integration (NumPy)
│   ├── prediction.py             # soc curve, best/worst, confidence
│   ├── speed.py                  # efficiency band optimizer
│   ├── charging.py               # DP charge-stop optimizer
│   ├── timeline.py               # chapter generation
│   ├── twin.py                   # Kalman correction filter
│   └── types.py                  # VehicleSpec, TripContext, RouteSamples …
├── app/
│   ├── main.py                   # app factory; role from GRADIENT_ROLE=api|ws|worker
│   ├── core/                     # settings, db, redis, security, problem+json, otel
│   ├── modules/
│   │   ├── auth/      {router.py, service.py, repo.py, schemas.py}
│   │   ├── users/     …           # every module: router (HTTP), service (facade,
│   │   ├── vehicles/  …           #   the ONLY cross-module entry), repo (SQL),
│   │   ├── navigation/…           #   schemas (DTOs), internal/* (private)
│   │   ├── elevation/ …
│   │   ├── energy/    …           # thin adapter: DB/context → gradient_energy calls
│   │   ├── charging/  …
│   │   ├── weather/   …
│   │   ├── traffic/   …
│   │   ├── trips/     …
│   │   ├── reports/   …
│   │   ├── community/ …
│   │   ├── gamification/…
│   │   ├── notifications/…
│   │   ├── analytics/ …
│   │   └── voice/     …
│   ├── ws/                        # drive-session gateway (role=ws)
│   │   ├── session.py             # connection lifecycle, resume tokens
│   │   └── twin_runner.py         # 1 Hz loop per session
│   └── jobs/                      # arq task definitions (role=worker)
│       ├── charging_sync.py       # OCM/OCPI pulls (15 min)
│       ├── weather_sync.py        # grid refresh (1 h)
│       ├── coach.py               # post-trip report
│       ├── gamification.py        # achievements, leaderboards (hourly)
│       ├── partitions.py          # monthly partition + lake export
│       └── catalog.py             # vehicle catalog publishing
└── tests/                         # mirrors app/ + engine golden-trip suite
```

Import contracts (CI-enforced by import-linter):
`gradient_energy` imports nothing from `app`; `modules/*` import other modules only via
`modules/<x>/service.py`; `router.py` never imported by anyone.

## 3. Route-planning pipeline (synchronous, p95 ≤ 2.5 s)

```
POST /routes/plan
  → navigation.plan()                       orchestrator
      1. cache check (request_hash, Redis)                     ~1 ms
      2. ORS candidates (parallel httpx, timeout 1.2 s)        ~600 ms
      3. decode + resample 25 m                                ~20 ms
      4. elevation.batch(points)   Redis→PG→Mapbox (parallel)  ~50–400 ms
      5. weather.along_route(ETA-shifted)   Redis grid         ~10 ms
      6. traffic speeds per segment                            ~50 ms
      7. gradient_energy: smooth→slope→energy→prediction       ~50 ms
      8. charging.optimize (only if arrival < reserve)         ~100 ms
      9. timeline + scores + bundle assembly; samples → S3     ~30 ms
     10. persist route row; return bundles
```

All candidates processed concurrently (`asyncio.gather`). Elevation cold-cache worst case
(long route, no tiles) is the latency driver → tile prefetch job warms popular corridors.

## 4. Live drive loop (role=ws)

Per session, a `TwinRunner` task at 1 Hz:

```
GPS batch → map match (against active route only)
         → observed vs predicted power (trailing 60 s)
         → Kalman-filtered calibration factor
         → remaining-route re-scale (vectorized, cheap)
         → display smoothing contract (≤0.5 %/s slew)
         → emit twin frame + queued voice cues
```

Session state (twin vector, filter state, resume token) lives in Redis hash, TTL 2 h —
WS pods are stateless and horizontally scalable; reconnect resumes seamlessly. Full
re-simulation (weather refresh, reroute) is throttled to ≥ 30 s intervals or on events.

## 5. Background jobs (arq)

| Job | Schedule | Notes |
|---|---|---|
| charging_sync | 15 min | delta-sync OCM; OCPI push webhooks where offered |
| weather_sync | 1 h | Open-Meteo grid for active regions |
| coach | on trip close | ideal-driver re-sim + report + push |
| gamification | hourly | achievement rules, weekly leaderboards |
| tile_prefetch | daily | top corridors' DEM tiles |
| partitions/lake export | monthly | trip_samples → parquet |
| catalog publish | on release | vehicle_models → CDN JSON |

Jobs are idempotent (natural keys / upserts) and observable (Prometheus job metrics).

## 6. External integrations (all behind adapter interfaces)

| Adapter | Provider | Fallback |
|---|---|---|
| RoutingAdapter | OpenRouteService | Valhalla (Beta), Mapbox Directions |
| ElevationAdapter | Mapbox Terrain-DEM | Google Elevation API |
| WeatherAdapter | Open-Meteo | Met.no |
| TrafficAdapter | Mapbox Traffic | none (degrade to freeflow) |
| ChargerAdapter | OCM + OCPI + NREL | cached snapshot |
| LLMAdapter | Anthropic API | canned-intent fallback |
| PushAdapter | FCM + APNs | — |

Each adapter: httpx client with timeout, retry (tenacity, jittered, ≤2), circuit breaker,
and a `degraded` result type — the pipeline must always return a bundle, flagging which
inputs were stale/missing (`bundle.data_quality` flags surface in UI as reduced confidence).

## 7. Observability

- OpenTelemetry traces (FastAPI + SQLAlchemy + httpx instrumentation) → Grafana Tempo.
- Prometheus metrics: pipeline stage latency histograms, cache hit ratios, WS sessions,
  prediction-error gauge (predicted vs actual at trip close — the product's north star).
- Sentry for exceptions (both backend and Flutter), release-tagged.
- Structured JSON logs (structlog): request_id, user_id (hashed), route_id; no coordinates
  at info level (GDPR); CloudWatch → Grafana Loki at scale.

## 8. Performance budgets

| Path | Budget (p95) |
|---|---|
| /routes/plan (300 km, cold) | 2.5 s |
| /routes/plan (cached) | 150 ms |
| twin frame compute | 20 ms |
| /chargers bbox | 120 ms |
| any OLTP query | 20 ms |
