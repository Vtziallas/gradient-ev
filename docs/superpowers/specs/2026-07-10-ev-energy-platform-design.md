# Gradient — EV Energy Navigation Platform: Master Design Document

**Date:** 2026-07-10
**Status:** Draft for review
**Working title:** Gradient (codename; energy + slope)

---

## 1. Vision

Every navigation app answers "how do I get there fastest?" Gradient answers a question no
mainstream app answers: **"what will this road do to my battery, and why?"**

The product is an energy-first navigation platform for EVs that:

- Renders the route as an **animated 3D terrain** where color = energy, not traffic.
- Replaces the distance axis with an **Energy Timeline** (gains, losses, charges).
- Computes a **physics-based battery prediction** (not ML guesswork) with confidence bounds.
- Recommends a **safe efficiency speed band**, never encouraging speeding.
- Runs a **digital twin** of the vehicle that corrects itself against reality every second.
- Coaches the driver after every trip with concrete, quantified feedback.

Reference experience: Tesla's trip energy planner + Apple Maps polish + Waze community +
flight-sim terrain + an AI coach — as one coherent product.

## 2. Scope decomposition

This request describes a platform, not a feature. Per good practice it is decomposed into
sub-systems, each with its own detailed spec in `docs/`:

| Sub-system | Spec | Owner module(s) |
|---|---|---|
| System architecture, AI/GIS/3D architecture, scalability | [Architecture.md](../../Architecture.md) | all |
| Data model (PostgreSQL + PostGIS) | [Database.md](../../Database.md) | all |
| Public API + realtime protocol | [API.md](../../API.md) | backend |
| Physics energy engine, battery prediction, speed optimizer | [EnergyEngine.md](../../EnergyEngine.md) | energy |
| Backend service design (FastAPI modular monolith) | [BackendArchitecture.md](../../BackendArchitecture.md) | backend |
| Flutter app architecture, offline-first, 3D rendering | [MobileArchitecture.md](../../MobileArchitecture.md) | mobile |
| UX wireframes, component hierarchy, design language | [UX.md](../../UX.md) | design |
| Security, auth, GDPR | [Security.md](../../Security.md) | security |
| Cloud, IaC, CI/CD, monitoring, logging, cost | [Deployment.md](../../Deployment.md) | devops |
| Testing strategy and validation | [Testing.md](../../Testing.md) | qa |
| Milestones, risks, tech debt, monetization, marketing | [Roadmap.md](../../Roadmap.md) | product |

Build order (each is a separate spec → plan → implement cycle):

1. **Energy Engine** (pure Python library; the moat, testable in isolation)
2. **Backend core** (auth, vehicles, route pipeline wrapping the engine)
3. **Mobile MVP** (planning UI, 3D route, energy timeline, prediction display)
4. **Live drive loop** (WebSocket telemetry, digital twin correction, voice)
5. **Charging optimizer + community + gamification**
6. **Web dashboard** (Next.js + CesiumJS trip replay / fleet)

## 3. Locked decisions (from requirements)

- Mobile: **Flutter + Riverpod**, Clean Architecture, feature-first, offline SQLite.
- Backend: **FastAPI (Python)**, modular monolith — *not* microservices initially.
- Data: **PostgreSQL + PostGIS**, **Redis**, Docker, AWS, Terraform, GitHub Actions.
- Maps: Mapbox (SDK, Terrain-DEM, Navigation), OSM, OpenRouteService, Google Elevation fallback.
- Energy model: **physics first, ML later** — deterministic equations at 25–50 m resolution.
- Web: Next.js + Three.js + CesiumJS.
- Monitoring: Prometheus, Grafana, Sentry.

## 4. Judgment calls (where requirements were silent)

These are decisions I made and expect challenge on during review:

| Decision | Choice | Why |
|---|---|---|
| Routing engine | OpenRouteService (hosted) for MVP → self-hosted **Valhalla** at Beta | ORS is fastest to integrate; Valhalla gives cost-model control (energy-weighted routing) and removes rate limits. |
| Elevation source | Mapbox Terrain-DEM RGB tiles, server-side decode, cached in Redis + Postgres; Google Elevation as fallback only | One provider for both rendering and physics keeps the mesh and the math consistent. |
| Charging data | Open Charge Map + OCPI feeds (per-operator), NREL for US | No single global source exists; OCM is the broadest free base layer. |
| 3D on mobile (MVP) | Mapbox GL 3D terrain + draped energy-colored route + scripted camera; custom `flutter_gpu` energy-ribbon shader is a fast-follow | Shipping a custom terrain engine in MVP is the #1 schedule risk; Mapbox terrain gets 90% of the wow at 5% of the cost. Full custom mesh stays in the architecture. |
| Telemetry ingestion | 1 Hz client-side aggregation, batched to server every 15 s over WebSocket; raw 1 Hz kept on device | Bandwidth + battery + GDPR minimization; server never needs raw GPS at 1 Hz. |
| Background jobs | **arq** (Redis-based, asyncio-native) | Celery is heavier and sync-flavored; arq matches FastAPI's async model. |
| ORM / migrations | SQLAlchemy 2.0 (async) + Alembic | Industry default, PostGIS support via GeoAlchemy2. |
| Mobile DB | Drift (SQLite) | Type-safe, reactive queries, solid Flutter support. |
| Weather | Open-Meteo (primary, free, good gridded forecast incl. wind at altitude) + Met.no fallback | Per-segment forecast lookup along route at ETA-shifted times. |
| Voice AI | Server-side LLM (Claude via Anthropic API) with function-calling into our own APIs; on-device wake/STT via platform speech APIs | Voice answers require live route/battery context — that lives server-side. |
| Payments | RevenueCat wrapping StoreKit/Play Billing | Subscription tiers without building entitlement infra. |
| Vehicle spec catalog | Curated internal `vehicle_models` table seeded from public spec data (EV Database-style attributes), human-verified | Physics accuracy depends on Cd·A, mass, usable kWh — must be curated, not scraped blindly. |

## 5. Approaches considered

**A. Full custom 3D engine + energy-weighted custom router from day one.**
Maximum differentiation, 12+ months to first release, high burn. Rejected for MVP.

**B. Thin wrapper over Mapbox/ABRP-style APIs, no own physics.**
Fast but no moat; predictions can't be explained or corrected. Rejected — the physics engine
*is* the product.

**C. (Chosen) Own physics engine + commodity routing/tiles + Mapbox terrain rendering, with
a pre-planned migration path to custom router (Valhalla cost model) and custom ribbon
renderer.** The moat (energy engine, digital twin, explanations) is built in-house from day
one; everything commodity is bought. Every "buy" has a named "build" successor in Roadmap.md.

## 6. Non-goals (MVP)

- No OBD-II / manufacturer API ingestion (manual battery % + vehicle model instead).
- No ML models (physics only; telemetry is collected *for* future ML).
- No AR, wearables, V2G, fleet, insurance (Roadmap.md → Future).
- No turn-by-turn voice guidance beyond energy events (Mapbox Nav SDK handles maneuvers).

## 7. Engineering operating model (AI agents)

Work is executed by specialized agents, each owning a module and its docs, coordinated by an
orchestrator. Mapping to this repo's tooling: each agent = a scoped subagent definition in
`.claude/agents/` created when implementation starts; the orchestrator is the main session
executing per-module implementation plans (superpowers:writing-plans →
subagent-driven-development).

| Agent | Owns | Primary spec |
|---|---|---|
| Architecture | module boundaries, ADRs | Architecture.md |
| Backend | FastAPI app, API contracts | BackendArchitecture.md, API.md |
| Database | schema, migrations, PostGIS | Database.md |
| Energy Engine | physics, prediction, validation | EnergyEngine.md |
| GIS / Terrain | elevation, sampling, map matching | Architecture.md §GIS |
| 3D Graphics | shaders, meshes, camera | MobileArchitecture.md §3D |
| Flutter | mobile app | MobileArchitecture.md |
| Charging | charging optimizer + data feeds | EnergyEngine.md §Charging, API.md |
| Weather | weather ingestion + impact model | EnergyEngine.md §Weather |
| Navigation | routing, comparison | Architecture.md §Routing |
| Battery Scientist | battery model params, degradation | EnergyEngine.md §Battery |
| Optimization | speed band, charge-stop MILP/DP | EnergyEngine.md §Optimization |
| QA | Testing.md, validation datasets | Testing.md |
| Performance | budgets, load tests | Testing.md, Deployment.md |
| Security | Security.md, reviews | Security.md |
| DevOps | Terraform, CI/CD, monitoring | Deployment.md |
| UX Designer | wireframes, design system | UX.md |
| Documentation | docs freshness | all |
| Code Reviewer | every PR | — |

Rules: every agent produces/updates documentation with its code; no cross-module imports
except via module public interfaces; the orchestrator merges only green, reviewed work.

## 8. Success criteria

- **Prediction accuracy:** arrival SoC error ≤ ±3% on 90% of validated trips (Beta gate).
- **Route pipeline latency:** ≤ 2.5 s p95 for a 300 km route, 3 candidates, cold cache.
- **3D experience:** 60 FPS sustained on mid-tier devices, 120 FPS on flagships.
- **Trust:** every number on screen must be explainable on tap ("why?").
- **No sudden jumps:** displayed SoC prediction never moves > 0.5 %/s (smoothing contract).

## 9. Risks (top 5 — full analysis in Roadmap.md)

1. **Physics accuracy without OBD data** — mitigations: curated vehicle catalog, conservative
   confidence bands, per-user calibration factor learned from trip closure reports.
2. **Mapbox cost at scale** — mitigations: aggressive tile caching, offline packs, planned
   self-hosted Valhalla + protomaps escape hatch.
3. **3D scope creep** — mitigation: MVP locked to Mapbox terrain path; custom shaders gated
   behind a milestone.
4. **Charging data reliability** — mitigation: community reports weighted into a per-station
   reliability score; never single-source.
5. **Battery-prediction liability** ("app said I'd make it") — mitigation: worst-case is the
   headline number below 15% margin; legal disclaimer; charge-stop bias to safety.

---

*Detailed sections live in the linked specs. Review flow: read Architecture.md first, then
EnergyEngine.md (the core IP), then the rest in any order.*
