# Gradient — Testing Strategy

Philosophy: the energy engine is tested like avionics; the app is tested like a consumer
product; the integrations are tested like they will fail (because they will).

## 1. Energy engine (highest bar)

- **Golden trips:** versioned dataset (`testdata/golden_trips/`) of real logged EV trips
  (public OBD datasets, team vehicles, later consenting beta users) with route, weather,
  vehicle, observed SoC curve. CI gates: arrival SoC MAE ≤ 3 %, per-10 km MAE ≤ 1.5 %.
  Any engine PR that shifts golden results requires an `engine_version` bump + changelog.
- **Property-based tests (Hypothesis):** energy conservation, regen ≤ potential energy,
  monotonicity in mass/wind/grade, integration invariance to sample spacing (25 vs 50 m
  within tolerance), SoC never NaN/negative.
- **Analytical fixtures:** flat-road constant-speed closed-form solutions; single-hill
  round trips; textbook drag/rolling values per vehicle class.
- **Cross-language contract:** the Dart offline-engine subset runs the same golden vectors
  as the Python engine; outputs must match within 0.1 % SoC (generated test vectors
  shipped in `packages/route_bundle`).
- **Optimizer tests:** speed band never exceeds limit (unwaivable), charge plan never
  violates reserve SoC, DP optimality vs brute force on small graphs.

## 2. Backend

- Unit: module services with in-memory repos; adapters against recorded fixtures (vcr-style
  cassettes for ORS/Mapbox/Open-Meteo/OCM).
- Integration: testcontainers (Postgres+PostGIS, Redis); full pipeline test:
  plan request → bundle assertions (timeline chapters sane, colors match thresholds).
- Contract: OpenAPI schema diff gate; generated clients compile.
- Chaos-lite: adapter failure injection — every external outage must degrade, never 500
  (bundle `data_quality` flags asserted).
- Load (k6, staging): 100 rps plan mix, 5 k concurrent WS sessions; budgets from
  BackendArchitecture §8 asserted as thresholds.
- Security: authz cross-tenant suite, rate-limit tests, dependency scanning in CI.

## 3. Mobile

- Unit: usecases, sync/outbox, codecs, offline rescale engine (golden vectors).
- Widget: timeline, speed bubble, prediction card, HUD — fake `TwinFrame` streams incl.
  the smoothing contract (no rendered jump > 0.5 %/s).
- Golden (screenshot): design-system components + key screens, light/dark, 2 locales.
- Integration (device farm — Firebase Test Lab): plan→drive happy path against fixture
  server; offline scenarios (airplane-mode mid-drive); background/kill/resume of drive
  session; battery drain measurement (≤ 8 %/h navigation budget).
- 3D performance: frame-time capture on device matrix (min spec: 2021 mid-tier Android);
  60 FPS p95 gate on route result screen.

## 4. Terrain & GIS validation

- Elevation pipeline vs surveyed benchmark points (national geodetic marks) — MAE ≤ 5 m
  raw, smoothed profile preserves total ascent within 5 %.
- Bridge/tunnel artifact suite: known problem geometries must not produce phantom
  climbs (smoothing regression pack).
- Map matching: recorded GPS traces with ground-truth routes, ≥ 99 % correct segment
  assignment, off-route detection latency ≤ 5 s.

## 5. Release gates

| Gate | Threshold |
|---|---|
| Engine golden trips | MAE limits above |
| Backend integration + load | budgets green |
| Mobile crash-free (staged rollout 10 %) | ≥ 99.5 % |
| Prediction error telemetry (staging fleet) | daily MAE ≤ 4 % |
| Security review | no high findings open |

Staged rollouts (10 % → 50 % → 100 %) with feature flags; any gate red = halt, not waive.
