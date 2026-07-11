# Gradient — Deployment, DevOps & Cost

## 1. Environments

`dev` (ephemeral per-PR preview optional) → `staging` (prod-shaped, scaled down) → `prod`
(eu-central-1). One Terraform root per env, shared modules; no console changes ever.

## 2. AWS topology (prod)

| Component | Service | MVP sizing |
|---|---|---|
| API / WS / worker | ECS Fargate, 3 services from one image (`GRADIENT_ROLE`) | 2×0.5 vCPU api, 2×0.5 ws, 1×0.5 worker, autoscale to 10 |
| DB | RDS PostgreSQL 16 + PostGIS, Multi-AZ | db.t4g.large, 100 GB gp3; read replica at Beta |
| Cache/queues | ElastiCache Redis 7 | cache.t4g.small ×2 |
| Object store | S3 (samples, lake, exports) + lifecycle to IA/Glacier | — |
| Edge | CloudFront (catalog, sample files, dashboard) + ALB | — |
| DNS/TLS | Route53 + ACM | — |
| Analytics lake | Kinesis Firehose → S3 → Athena | — |
| Secrets | Secrets Manager + KMS | — |

Terraform modules: `network`, `ecs-service`, `rds`, `redis`, `cdn`, `observability`,
`secrets` — each with staging/prod tfvars; state in S3 + DynamoDB lock; `terraform plan`
posted on PRs (Atlantis-style via Actions), apply on merge with manual approval for prod.

## 3. CI/CD (GitHub Actions)

```
PR:    ruff + mypy + import-linter → unit tests (engine golden trips gate)
       → integration tests (testcontainers PG+Redis) → build image → Trivy scan
       → flutter analyze + test + goldens → openapi diff (breaking-change gate)
merge→main:  deploy staging (ECS rolling) → smoke suite → tag
release tag: prod deploy = blue/green (CodeDeploy) with auto-rollback on
             CloudWatch alarms (5xx, latency, prediction-error spike)
mobile:      Actions → Fastlane → TestFlight / Play internal on main;
             store release trains every 2 weeks; feature flags (config endpoint)
             decouple deploy from release
db:          Alembic migrations run as pre-deploy ECS task; expand-migrate-contract
             pattern mandatory (no breaking migration with old code live)
```

## 4. Monitoring & logging

- **Metrics:** Prometheus (ECS scrape) → Grafana Cloud (managed; self-host post-Scale).
  Dashboards: API golden signals, pipeline stage latencies, cache hit ratios, WS sessions,
  external adapter error/circuit state, **prediction-error histogram** (north star),
  Mapbox/API spend counters (cost as a metric).
- **Alerts (PagerDuty):** p95 plan latency > 4 s, 5xx > 1%, DB CPU > 80%, adapter circuit
  open > 10 min, prediction MAE daily > 4%, budget anomaly.
- **Traces:** OTel → Tempo; **Logs:** structured JSON → CloudWatch → Loki; 30 d retention
  (14 d for anything location-adjacent).
- **Errors:** Sentry (backend + Flutter + Next.js), release health, crash-free-users SLO
  ≥ 99.5%.
- SLOs: API availability 99.9%, plan success rate 99.5%, WS session continuity 99%.

## 5. Cost estimation (monthly, EUR)

| Stage | Users (MAU) | AWS | Mapbox | Other APIs (weather/LLM/OCM) | Total |
|---|---|---|---|---|---|
| MVP/Alpha | 1 k | ~450 | free tier–200 | ~100 | **~750** |
| Beta | 25 k | ~1 800 | ~1 500 (tiles+nav sessions) | ~600 | **~3 900** |
| Production | 100 k | ~5 500 | ~6 000 | ~2 000 | **~13 500** |
| Scale | 500 k | ~18 000 | ~20 000* | ~6 000 | **~44 000** |

*Mapbox dominates at scale → contractual pricing + self-hosted Valhalla/protomaps escape
hatch is a planned cost lever (Roadmap). Unit economics target: infra ≤ €0.10/MAU/month.

## 6. Disaster recovery

RDS automated backups (PITR, 14 d) + nightly logical dump to S3 cross-region; Redis is
reconstructable (cache-only design); infra re-creatable from Terraform in < 2 h.
RTO 4 h / RPO 15 min. Game-day restore drill each quarter.
