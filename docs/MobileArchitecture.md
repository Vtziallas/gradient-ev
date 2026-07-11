# Gradient — Mobile Architecture (Flutter)

## 1. Stack

Flutter (stable channel, Impeller), Riverpod 2 (codegen), Drift (SQLite), Mapbox Maps
Flutter SDK + Mapbox Navigation, `flutter_gpu` custom shaders (Stage 2 ribbon), dio +
generated OpenAPI client, web_socket_channel, freezed models, go_router, RevenueCat,
platform speech APIs (STT/TTS), Sentry Flutter.

## 2. Clean Architecture, feature-first

```
mobile/
├── lib/
│   ├── app/                    # bootstrap, router, theme, l10n, flavors
│   ├── core/                   # shared kernel — kept deliberately small
│   │   ├── network/            # dio, auth interceptor, connectivity
│   │   ├── db/                 # drift database, migrations
│   │   ├── sync/               # outbox queue, idempotency keys
│   │   ├── location/           # GPS service abstraction
│   │   └── design/             # tokens, components (see UX.md)
│   ├── features/
│   │   ├── auth/
│   │   │   ├── domain/         # entities, repository interface, usecases
│   │   │   ├── data/           # repo impl: remote (API) + local (drift)
│   │   │   └── presentation/   # screens, widgets, providers (Riverpod)
│   │   ├── garage/             # vehicle selection & specs
│   │   ├── planning/           # search, route plan, comparison
│   │   ├── route3d/            # terrain view, camera director, ribbon renderer
│   │   ├── timeline/           # energy timeline UI
│   │   ├── drive/              # live navigation, twin HUD, speed bubble, voice
│   │   ├── charging/           # charger browse/detail, plan editing
│   │   ├── trips/              # history, coach reports
│   │   ├── community/          # reports, voting
│   │   ├── gamification/       # achievements, leaderboards
│   │   └── settings/           # profile, units, privacy, subscription
│   └── main_{dev,staging,prod}.dart
├── packages/
│   ├── api_client/             # generated from openapi.json — never hand-edited
│   └── route_bundle/           # RouteEnergyBundle + protobuf sample codec (shared types)
└── test/  integration_test/
```

Dependency rule: presentation → domain ← data; features import `core` and other features'
**domain** interfaces only. Enforced with `dart_code_metrics` banned-imports config.

## 3. State management (Riverpod)

- **Server cache providers:** `FutureProvider.family` per resource keyed by id + params,
  backed by repository (SQLite-first, network refresh) — server state is never duplicated
  into hand-rolled stores.
- **Session state:** `driveSessionProvider` — a `StateNotifier` running the WS client and
  exposing an immutable `TwinFrame` stream; UI widgets select slices
  (`select((f) => f.speedBand)`) so 1 Hz updates repaint only affected widgets.
- **3D scene state:** `route3dControllerProvider` — camera mode (flyThrough / orbit /
  follow / free), exaggeration, playhead; the renderer is a consumer, never an owner, of
  state (replay and tests drive the same provider).
- **Ephemeral UI:** local `StateProvider`/widget state; never global.

## 4. Offline-first strategy

Principle: **the plan you made is always available; new computation needs network.**

- **Route bundles pinned:** planning a route stores the full bundle + protobuf samples in
  Drift; active + last 10 routes survive offline, including 3D terrain data already
  downloaded as Mapbox offline pack for the route corridor (auto-created on plan, ~corridor
  buffer 5 km, capped 200 MB LRU).
- **On-device engine subset:** a Dart port of the *integration* step (not the full
  pipeline) re-scales the stored prediction using the live calibration factor when offline
  — the twin degrades gracefully rather than freezing; confidence indicator drops and UI
  shows "offline estimate".
- **Vehicle catalog + achievements + trip history:** fully cached, TTL-refreshed.
- **Outbox pattern:** all writes (trip close, community reports, votes, settings) enqueue
  into a Drift `outbox` table with idempotency keys; a sync worker drains on connectivity,
  server upserts make retries safe. Conflict policy: server authoritative for computed
  data; last-write-wins for user preferences; community reports are append-only.
- **Telemetry buffering:** 1 Hz samples buffer locally during connectivity gaps and batch-
  upload on reconnect (bounded to 24 h, oldest dropped).

## 5. 3D route view (feature `route3d`)

- **Stage 1 (MVP):** Mapbox terrain + `line-gradient` energy route + camera director:
  - *Fly-through:* precomputed keyframe path above route (altitude ∝ segment length,
    look-ahead easing), plays on plan completion; scrubbing linked to Energy Timeline.
  - *Orbit / follow / free:* gesture-driven modes; exaggeration slider 1–3× bound to the
    terrain source property; time-of-day light + sky layer for shadows.
  - HUD overlay (Flutter widgets, not map layers): current/next elevation, slope %,
    distance to summit/downhill, energy required/recovered, predicted SoC at cursor.
- **Stage 2:** `flutter_gpu` energy ribbon (Architecture.md §6) as a texture-composited
  overlay; animated vehicle glTF; energy-flow pulse shader. Ships behind a feature flag;
  Stage 1 remains the fallback for low-end devices (device-class gate).
- Frame budget: HUD rebuilds decoupled from map rendering; 1 Hz twin frames animate via
  implicit animations (no jank between updates); target 60 FPS mid-tier / 120 FPS
  ProMotion.

## 6. Drive mode (feature `drive`)

Screen composition: Mapbox Navigation (maneuvers, lane guidance) + Gradient energy layer
(speed bubble, energy timeline rail on screen edge, twin HUD). Voice: platform STT → text →
`/voice/query` (SSE) → platform TTS; energy voice cues from twin frames are throttled
(≥ 90 s between non-critical cues) and never overlap maneuver instructions (Mapbox audio
focus arbitration). Background operation: iOS background location + audio session; Android
foreground service with navigation notification. Battery target: ≤ 8%/h app drain during
navigation (measured in CI device farm).

## 7. Error & degraded states (contract with UX)

Every feature defines its degraded ladder, e.g. drive mode:
full twin → offline estimate (local rescale) → static plan (no GPS) → map-only.
No feature may render a blank/spinner state when cached data exists; staleness is shown as
a badge + reduced confidence, never hidden.

## 8. Testing (see Testing.md for full strategy)

- Unit: usecases, codecs, offline engine subset vs Python engine golden vectors
  (same inputs → same SoC curve within tolerance — cross-language contract test).
- Widget: timeline, speed bubble, HUD with fake twin streams.
- Integration: plan→drive happy path against a recorded-API fixture server; offline
  scenario suite (airplane mode toggles) on device farm.
- Golden tests for design-system components in light/dark.
