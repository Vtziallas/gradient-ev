# Gradient — Roadmap, Business & Risk

## 1. Milestones

### M1 — MVP (16 weeks, ~5 engineers)
**Goal:** prove the core promise — plan a route and *understand* its energy story.
**Deliverables:** auth + garage (curated catalog ~60 models), route planning (3 candidates),
elevation/energy pipeline, battery prediction with confidence, Energy Timeline, 3D route
(Mapbox terrain stage 1, fly-through/orbit/follow/exaggeration), charging suggestions (DP
optimizer), safe speed band, offline route pinning, trip history (manual start/stop),
staging+prod infra, stores' internal tracks.
**Effort:** backend 2, mobile 2, full-stack/devops 1. **Dependencies:** Mapbox contract,
ORS quota, OCM ingestion, vehicle catalog curation (start week 1 — long pole).
**Risks:** 3D scope creep (mitigation: stage 1 lock), catalog accuracy (curate top-selling
EVs first).

### M2 — Alpha (8 weeks)
**Goal:** live driving works end-to-end for internal + 100 invited users.
**Deliverables:** WS drive sessions, digital twin correction + smoothing contract, drive
HUD + speed bubble, voice cues (TTS), trip telemetry ingestion, eco coach v1, Sentry/
dashboards complete, golden-trip validation harness with ≥ 200 real trips.
**Risks:** prediction accuracy in cold weather (winter test plan), background GPS on iOS.

### M3 — Beta (10 weeks, public, 1 region e.g. Greece/Germany)
**Goal:** accuracy + reliability at consumer quality; monetization live.
**Deliverables:** per-user calibration, charging cost/wait models, community reports,
gamification v1, voice Q&A (LLM), Next.js dashboard (trip replay, CesiumJS), subscriptions
(RevenueCat), GDPR export/erasure flows, load-tested to 25 k MAU, Valhalla spike.
**Exit gate:** arrival SoC MAE ≤ 3 % on 90 % of beta trips; crash-free ≥ 99.5 %.

### M4 — Production (8 weeks)
**Goal:** multi-country launch. Localization (5 languages), OCPI operator integrations,
external pentest, marketing site, store featuring push, energy ribbon (stage 2 3D) as
flagship visual, referral program. **Risks:** support load (in-app help + status page),
charging data gaps per country.

### M5 — Scale (ongoing)
Valhalla energy-costed routing in prod, protomaps/tile cost lever, ML residual models,
read replicas + module split as load dictates (drive-session first), fleet/B2B pilot,
OBD-II + manufacturer APIs (Smartcar-style), Android Auto / CarPlay.

## 2. Monetization & tiers

| | Free | **Plus €4.99/mo** | **Pro €9.99/mo** |
|---|---|---|---|
| Route energy planning | 5/day | unlimited | unlimited |
| 3D terrain | fly-through only | full interactive | full + energy ribbon |
| Battery prediction | point estimate | + best/worst + confidence | + per-user calibration |
| Charging optimizer | 1 stop simple | full DP + costs + wait | + price alerts, plug-share |
| Drive twin + speed bubble | — | ✓ | ✓ |
| Eco coach | monthly summary | per-trip | + battery health insights |
| Voice AI | — | 20 queries/mo | unlimited |
| Trip replay (web) | — | — | ✓ |
Annual = 2 months free. B2B fleet per-vehicle pricing (Scale). Principle: safety features
(worst-case warnings, reserve enforcement) are **never** paywalled.

## 3. Marketing strategy (condensed)

Positioning: *"The first navigation app that shows you energy, not just roads."*
Wedge: EV YouTube/forum community (fly-through videos are inherently shareable — every
planned route is a marketing asset; built-in "share 3D route video" export). Launch in
mountainous EV-dense markets (Norway, Switzerland, Austria) where the problem is visceral.
Partnerships: charging networks (reliability data swap), EV rental fleets. Content: winter
range tests publishing our prediction vs actual — accuracy *is* the campaign.

## 4. Risk analysis

| Risk | L×I | Mitigation |
|---|---|---|
| Prediction accuracy insufficient w/o OBD | H×H | golden-trip gate, conservative bands, calibration, worst-case-first UX |
| Mapbox cost/lock-in | M×H | usage caps, Valhalla+protomaps exit, cost-as-metric alerts |
| 3D perf on Android low-end | M×M | stage-1 fallback, device-class gating |
| Charging data quality | H×M | multi-source + community + reliability scoring |
| App-said-I'd-make-it liability | L×H | disclaimers, reserve enforcement, safety-first defaults |
| Apple/Google map platform response | M×M | move fast on the physics moat they won't build |
| Team scope creep (this spec is big) | H×H | milestone locks; anything not in M-scope goes to backlog |

## 5. Technical debt strategy

- Debt register in repo (`docs/debt.md`): every conscious shortcut logged with owner +
  sunset milestone (e.g. "ORS hosted → Valhalla by M5", "flat η map → per-model maps").
- 20 % of each milestone reserved for debt burn-down + platform work; debt items block
  the milestone after their sunset.
- ADRs make reversals cheap to reason about; import-linter keeps the monolith modular so
  the microservice split stays a refactor, not a rewrite.

## 6. Future roadmap (post-Scale, from requirements)

ML battery optimization → watchOS/Wear OS glanceables (arrival SoC on wrist) → CarPlay/
Android Auto (before XR) → AR windshield nav → Vision Pro / Android XR route sandbox →
fleet management + insurance scoring APIs → battery health prediction + predictive
maintenance → V2G scheduling, solar-aware home charging, calendar-aware pre-conditioning,
smart-home integration. Each enters as its own brainstorm→spec→plan cycle.
