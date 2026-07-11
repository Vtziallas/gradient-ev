# Gradient — Security Model

## 1. Authentication

- **Passwords:** argon2id (m=64 MiB, t=3), breach check (k-anonymity HIBP) on set.
- **OAuth:** Sign in with Apple + Google (OIDC id_token verification server-side; nonce).
- **Tokens:** access JWT 15 min (ES256, kid-rotated keys in AWS KMS), refresh 60 days,
  **rotating with family reuse detection** (reuse ⇒ revoke family, force re-login, alert).
- JWT claims minimal: `sub`, `sid`, `tier`, `exp`; no PII.
- Mobile storage: Keychain / EncryptedSharedPreferences (never SQLite/prefs for tokens).

## 2. Authorization

- Resource ownership enforced at repository layer (`WHERE user_id = :caller`) — not in
  handlers; multi-tenancy tests assert cross-user 404s.
- Roles: `user`, `moderator` (community), `admin` (catalog/ops) — claim-based, admin
  endpoints on a separate internal ALB listener + SSO (no public admin surface).
- Subscription entitlements (`tier`) validated server-side via RevenueCat webhooks; clients
  never gate features alone.

## 3. API protection

- Rate limiting (Redis sliding window): auth endpoints 5/min/IP; `/routes/plan`
  10/min/user (free) 60/min (pro); WS telemetry 1 msg/10 s min interval; 429 +
  `Retry-After`.
- Input validation: Pydantic strict mode; coordinate bounds; polyline length caps
  (≤ 1500 km route); request body ≤ 256 KB.
- OWASP ASVS L2 as the checklist baseline; headers (HSTS, CSP for dashboard), TLS 1.2+
  only, no CORS wildcard.
- Community content: rate limits, profanity/URL filtering, moderator queue, shadow-ban
  capability; report abuse weighting so brigading can't kill a charger's reliability score.
- Voice/LLM: allow-listed tools only, output grounded in tool results, prompt-injection
  containment (user text never concatenated into system prompt; tool results are typed
  JSON), per-user token budget.

## 4. Secrets & infrastructure

- AWS Secrets Manager + IAM task roles (no static keys in env/images); KMS envelope
  encryption; Terraform state encrypted with locked DynamoDB table.
- ECR image scanning + `pip-audit`/`osv-scanner` in CI; Dependabot; SBOM published.
- Network: private subnets for RDS/Redis; ALB only public component; security groups
  least-privilege; SSM Session Manager instead of SSH.

## 5. GDPR & privacy (location data = high sensitivity)

- **Minimization:** server stores 1 Hz telemetry only for the user's own trip features;
  ML lake exports are anonymized (user_id dropped, trip start/end snapped to 500 m and
  time-fuzzed — home/work protection).
- **Rights:** in-app export (machine-readable, async job) and erasure (30-day grace,
  hard-null PII, cascade per Database.md §10). Records of processing + DPIA maintained;
  location processing under consent (granular toggles: telemetry contribution, community,
  leaderboards — each independently off-switchable).
- Logs never contain raw coordinates or emails at info level; user_id hashed in logs.
- Data residency: EU region (eu-central-1) primary; US expansion = separate stack.
- Sub-processors documented (Mapbox, Anthropic, RevenueCat, Sentry, AWS) with DPAs.

## 6. Safety-adjacent security

- Battery predictions are advisory: legal disclaimer at onboarding; worst-case-first rule
  (EnergyEngine §3) is a product safety control, treated with test coverage like security.
- Speed recommendations hard-capped at legal limit **in the engine**, with a regression
  test that can never be waived.

## 7. Security program

- Threat model (STRIDE) maintained in repo, reviewed each milestone.
- `/security-review` on every PR touching auth/geo/payment paths; annual external pentest
  before Production milestone; vulnerability disclosure policy + security.txt.
