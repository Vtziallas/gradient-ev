# Gradient — EV Energy Navigation Platform

> The first navigation app that shows you **energy**, not just roads.

Physics-based battery prediction, animated 3D terrain routes, an Energy Timeline, a live
digital twin, and an eco coach — the definitive EV companion.

**Status:** specification phase. No implementation yet.

## Specification

Start here: [Master design doc](docs/superpowers/specs/2026-07-10-ev-energy-platform-design.md)
— vision, scope decomposition, locked decisions, judgment calls, risks.

| Doc | Covers |
|---|---|
| [Architecture.md](docs/Architecture.md) | System/GIS/AI/3D architecture, modules, caching, scalability |
| [EnergyEngine.md](docs/EnergyEngine.md) | Physics model, battery prediction, digital twin, speed band, charging optimizer, validation |
| [Database.md](docs/Database.md) | Full PostgreSQL/PostGIS schema, retention |
| [API.md](docs/API.md) | REST + WebSocket contracts, RouteEnergyBundle |
| [BackendArchitecture.md](docs/BackendArchitecture.md) | FastAPI modular monolith, folder structure, pipelines, jobs |
| [MobileArchitecture.md](docs/MobileArchitecture.md) | Flutter clean architecture, Riverpod, offline-first, 3D rendering |
| [UX.md](docs/UX.md) | Wireframes, component hierarchy, design language |
| [Security.md](docs/Security.md) | Auth, authz, OWASP, GDPR |
| [Deployment.md](docs/Deployment.md) | AWS/Terraform, CI/CD, monitoring, cost |
| [Testing.md](docs/Testing.md) | Test strategy, golden trips, release gates |
| [Roadmap.md](docs/Roadmap.md) | Milestones, monetization, marketing, risks, tech debt |

## Stack (locked)

Flutter + Riverpod · FastAPI · PostgreSQL/PostGIS · Redis · AWS (ECS Fargate) · Terraform ·
GitHub Actions · Mapbox · Next.js/CesiumJS · Prometheus/Grafana/Sentry
