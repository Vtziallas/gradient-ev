# Gradient — System Architecture

## 1. Overview

Gradient is a **modular monolith** backend (FastAPI) serving a Flutter mobile app and a
Next.js web dashboard, backed by PostgreSQL/PostGIS + Redis, deployed on AWS via Terraform.

```
┌─────────────┐   ┌──────────────┐   ┌───────────────────┐
│ Flutter app │   │ Next.js web  │   │ 3rd-party feeds    │
│ (iOS/And.)  │   │ (dash/sim)   │   │ (OCM/OCPI, weather)│
└──────┬──────┘   └──────┬───────┘   └────────┬──────────┘
       │ HTTPS/WSS       │ HTTPS              │ pull jobs
┌──────▼─────────────────▼────────────────────▼──────────┐
│  AWS ALB → ECS Fargate                                  │
│  ┌────────────────────────────────────────────────────┐│
│  │ FastAPI modular monolith (api service)             ││
│  │  auth │ users │ vehicles │ navigation │ elevation  ││
│  │  energy │ charging │ trips │ reports │ community   ││
│  │  notifications │ analytics │ voice                 ││
│  └────────────────────────────────────────────────────┘│
│  ┌───────────────┐  ┌────────────────────────────────┐ │
│  │ worker service│  │ drive-session service (WSS)    │ │
│  │ (arq jobs)    │  │ same codebase, ws-only role    │ │
│  └───────────────┘  └────────────────────────────────┘ │
└───────┬───────────────┬───────────────┬────────────────┘
        │               │               │
  ┌─────▼─────┐   ┌─────▼─────┐   ┌─────▼─────┐
  │ RDS       │   │ Elasti-   │   │ S3        │
  │ Postgres  │   │ Cache     │   │ tiles,    │
  │ + PostGIS │   │ Redis     │   │ exports   │
  └───────────┘   └───────────┘   └───────────┘
```

One deployable image, three **roles** (`api`, `worker`, `ws`) selected by env var. This gives
monolith simplicity with independent scaling of the three load profiles — the classic
pre-microservices sweet spot.

## 2. Module map (modular monolith)

Each module is a Python package with a **public interface** (`module/service.py` exposing a
facade + Pydantic DTOs) and private internals. Cross-module calls go only through facades;
enforced by import-linter contracts in CI.

| Module | Responsibility | Depends on |
|---|---|---|
| `auth` | JWT/OAuth, sessions, refresh rotation | users |
| `users` | profiles, preferences, GDPR ops | — |
| `vehicles` | user vehicles + `vehicle_models` catalog | users |
| `navigation` | route candidates (ORS/Valhalla), polyline decode, map matching, comparison | elevation, energy, charging |
| `elevation` | DEM tile fetch/decode/cache, sampling, smoothing, slope | — |
| `energy` | physics engine, battery prediction, speed optimizer, energy timeline | vehicles, elevation, weather |
| `charging` | station data, availability, charge-stop optimizer, cost | energy |
| `weather` | forecast ingestion, per-segment weather at ETA | — |
| `traffic` | speed profiles per segment (Mapbox Traffic → community later) | — |
| `trips` | trip recording, telemetry ingestion, history | vehicles |
| `reports` | eco-coach analysis, efficiency scores | trips, energy |
| `community` | user reports (chargers, hazards), moderation, reliability scoring | users, charging |
| `gamification` | achievements, leaderboards, challenges | trips, reports |
| `notifications` | push (FCM/APNs), in-app inbox | users |
| `analytics` | product events, aggregates for dashboard | — |
| `voice` | LLM function-calling gateway over module facades | navigation, energy, charging |

**Microservice escape hatch:** the first candidates to split (when >~50 rps sustained or team
> ~15 engineers) are `drive-session` (already a separate role), `elevation` (CPU-bound,
cache-heavy), and `energy` (pure functions, trivially extractable). Module facades become
HTTP/gRPC clients; DTOs are already serializable. This is why facades are mandatory now.

## 3. GIS architecture

**Sampling pipeline** (the spine of the product):

1. `navigation` requests 1–3 candidate routes (ORS `driving-car`, alternatives on).
2. Decode polyline6 → resample to **25 m** points (50 m beyond 200 km routes) with
   cumulative distance; preserve maneuver/segment boundaries.
3. `elevation` batch-resolves elevations: lookup order Redis tile cache → Postgres
   `elevation_tiles` → Mapbox Terrain-DEM RGB tile fetch (zoom 14, decode
   `-10000 + (R·65536 + G·256 + B) · 0.1`) → Google Elevation API fallback. Tiles cached
   30 days (terrain is static).
4. **Smoothing:** Savitzky–Golay filter (window 11, order 3) over elevation series — removes
   DEM noise/bridges without flattening real grades; then slope
   `grade_i = Δh/Δs`, clamped to ±25%, and a second light smoothing pass on grade.
5. Segment classification: climb / descent / flat runs (grade threshold ±1%), summit
   detection, per-run aggregates (distance-to-summit, total ascent in run).
6. Hand the sampled, sloped route to `energy` (see EnergyEngine.md).

**Map matching (live loop):** Hidden-Markov-style matcher against the active route only
(not the whole graph): candidate = nearest points on route within 50 m, emission prob by GPS
accuracy, transition prob by heading + odometry. Off-route > 30 m for > 5 s ⇒ reroute.

**Spatial data:** all geometries stored as PostGIS `geography(*, 4326)`; heavy queries
(charger search along corridor) use `ST_DWithin` on a `ST_Buffer`ed route with GIST indexes.

## 4. Routing & comparison architecture

- MVP: OpenRouteService hosted API, profiles for fastest + shortest + "avoid-highways" as
  the third candidate. Each candidate runs the full energy pipeline; comparison dimensions
  (fastest / lowest energy / lowest charging cost / lowest elevation gain / highest regen /
  safest / most scenic) are **scores computed over the same candidates**, not separate
  router calls.
- Beta: self-hosted **Valhalla** with a custom costing model where edge cost =
  α·time + β·energy(edge) using a coarse per-edge energy estimate (grade from precomputed
  edge elevation, default vehicle) — true energy-optimal routing, our router differentiator.
- Scenic/safety scores: derived from OSM tags (tunnel, landuse, coastline proximity) and
  grade/curvature statistics; documented heuristics, versioned like code.

## 5. AI architecture

Three AI planes, deliberately separated:

1. **Deterministic plane (MVP):** physics engine, optimizers (speed band, charge stops).
   Pure functions, unit-testable, explainable. No ML.
2. **Learning plane (post-Beta):** telemetry lake (S3 parquet, partitioned by
   vehicle_model/region) feeds: per-user calibration factor (Bayesian update of a single
   consumption multiplier), then residual models (gradient-boosted trees on
   [grade, speed, temp, wind] → correction to physics prediction). ML **corrects** physics;
   it never replaces it — keeps explainability and cold-start behavior.
3. **Language plane:** `voice` module = LLM (Claude, function calling) with tools that map
   1:1 to module facades (`get_route_energy_breakdown`, `find_chargers`,
   `simulate_speed_change`…). The LLM never computes energy; it narrates engine output.
   Guardrails: allow-listed tools, per-user rate limit, responses grounded only in tool
   results.

**Digital twin** = the live drive session state machine (see BackendArchitecture.md §Drive
loop): predicted state vector (position, SoC, power) advanced by the physics engine,
corrected each second by observations via an error filter. "Twin" is a stateful projection,
not a separate system.

## 6. 3D rendering architecture

Two renderers, one data contract (`RouteEnergyBundle`, see API.md):

**Mobile (Flutter):**
- **Stage 1 (MVP):** Mapbox Maps Flutter SDK — 3D terrain (`raster-dem`), sky layer, energy-
  colored route line (`line-gradient` from per-sample energy class), draped charging-stop
  markers, scripted `flyTo`/`freeDrive` camera (fly-through, orbit, follow), terrain
  exaggeration property bound to a slider, dynamic light position by time-of-day.
- **Stage 2:** custom **energy ribbon** — an extruded route-corridor mesh (triangle strip,
  ~2 verts/sample) rendered via `flutter_gpu` custom shaders on top of Mapbox terrain:
  vertex shader lifts ribbon by elevation + exaggeration; fragment shader animates energy
  flow (scrolling emissive pulses toward the vehicle, speed ∝ power draw), regen segments
  pulse green toward the battery icon. Vehicle = low-poly glTF animated along the spline.
- Performance budget: ≤ 150k triangles in view, one draw call for the ribbon,
  camera-distance LOD (drop to 50/100 m sampling far away). Target 60 FPS mid-tier /
  120 FPS ProMotion flagships (frame pacing via Impeller).

**Web (CesiumJS):** quantized-mesh world terrain, same bundle drives a `Cesium` polyline
volume + particle energy flow; trip replay scrubs the timeline. Three.js only for non-geo
widgets (battery 3D, vehicle viewer).

**Color contract (both renderers):** green = regen (P_batt < −0.5 kW·class), yellow =
efficient (< 110% of vehicle baseline Wh/km), orange = 110–160%, red = >160% or grade >6%,
blue = charging stop. Thresholds computed per-vehicle by the engine and shipped in the
bundle so clients never re-derive physics.

## 7. State & data flow

- **Server state of record:** Postgres. Redis is cache + queues + WS session registry only —
  restartable with zero data loss.
- **Client state:** Riverpod graph (see MobileArchitecture.md); server data cached in SQLite
  with TTL + explicit route-bundle pinning for offline.
- **Realtime:** one WSS connection per drive session; server pushes twin corrections,
  client pushes telemetry batches. Fallback to HTTPS polling on WS failure.

## 8. Caching strategy (layers)

| Layer | What | TTL | Store |
|---|---|---|---|
| L1 device | route bundles, tiles (Mapbox offline packs), vehicle catalog | pinned / 7 d | SQLite + Mapbox cache |
| L2 Redis | DEM tiles (decoded arrays), weather grid cells, charger availability, route bundles by request-hash | 30 d / 1 h / 5 min / 10 min | Redis |
| L3 Postgres | elevation samples per road edge, charger static data | ∞ (versioned) | PostGIS |
| CDN | vehicle catalog JSON, app config, static tiles | 24 h | CloudFront |

Route request hash = (origin, dest, vehicle_model, options) rounded to 100 m grid — repeat
plans are near-free.

## 9. Scalability posture

- Stateless api/ws roles → horizontal ECS autoscaling on CPU + WS connection count.
- Postgres: RDS with read replica at Beta; telemetry tables partitioned monthly; heavy
  analytics offloaded to S3 parquet + Athena, never run on OLTP.
- The energy pipeline is CPU-bound Python → NumPy-vectorized over the whole sample array
  (no per-point Python loops); ~10k samples/route computes in <50 ms.
- Backpressure: route planning is synchronous (<2.5 s p95); everything else (reports,
  achievements, ingestion post-processing) is arq background jobs.

## 10. Architecture decision records

ADRs live in `docs/adr/NNNN-*.md`, one per irreversible decision; the table in the master
design doc (§4 judgment calls) seeds ADR-0001…0013 at implementation start.
