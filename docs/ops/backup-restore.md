# Backup and Restore

> **Status**: Template. `DECIDE` and `FILL IN` markers below are deliberate gaps. Resolve each as decisions are made.

> **Maturity**: MVP-stage. RDS automated backups + S3 versioning at default settings. Drill-tested before pilot launch.

---

## What gets backed up

| Asset | Backup mechanism | Retention | Recovery target |
|---|---|---|---|
| Postgres database (AWS RDS Mumbai) | RDS automated backups (point-in-time) + manual snapshots before risky migrations | **DECIDE**: retention period. Default suggestion: 30 days for automated; manual snapshots kept indefinitely until you delete them | RPO: **DECIDE** (default suggestion: 5 minutes); RTO: **DECIDE** (default suggestion: 1 hour) |
| S3 bucket (consents PDFs, any uploaded files) | S3 versioning + lifecycle rules | **DECIDE**: lifecycle policy. Default suggestion: keep all versions for 90 days, then transition to Glacier | RPO: 0 (versioning is real-time); RTO: minutes |
| Code repository | GitHub | Forever | RTO: minutes |
| Prompts (in repo) | GitHub | Forever | RTO: minutes |
| Cloudflare Workers config (`wrangler.toml`) | GitHub + Cloudflare account | Forever | RTO: minutes |
| Secrets | Stored in Cloudflare; **DECIDE**: backup strategy. **FILL IN**: secrets recorded out-of-band (e.g. 1Password vault) so loss of Cloudflare account isn't terminal |  | Critical — if lost, full reissue needed |

---

## What does NOT get backed up

- Local dev databases (each dev's responsibility)
- Cloudflare Workers Logs older than retention (Free tier: 7 days; Paid: longer)
- `llm_calls` table is in the main DB → covered by RDS backup
- HC snippets are in main DB → covered by RDS backup

---

## RDS backup configuration

> **FILL IN** when RDS instance is provisioned:

- Automated backups enabled: yes/no
- Backup window: **FILL IN** (suggestion: 17:00–18:00 UTC = 22:30–23:30 IST, low-traffic window)
- Backup retention period: **FILL IN** days (suggestion: 30)
- Multi-AZ: **DECIDE** (cost ~2x; not needed at MVP scale)
- Encryption at rest: **DECIDE** (suggestion: yes, AWS-managed key; required if DPDP scope expands)

---

## S3 backup configuration

> **FILL IN** when bucket is provisioned:

- Versioning: enabled
- Lifecycle rules: **FILL IN** (suggestion: noncurrent versions transition to Glacier after 30 days, expire after 365 days)
- Bucket name: **FILL IN** (e.g. `healthcoach-prod-content`)
- Encryption at rest: **DECIDE** (suggestion: yes, AWS-managed key)

---

## Restore procedures

### Postgres — point-in-time recovery

When: data corruption, accidental DROP, recent bad migration.

1. Identify the target timestamp (latest known-good state).
2. From AWS RDS console: select instance → "Restore to point in time".
3. **FILL IN**: target timestamp resolution (RDS supports 5-minute granularity by default).
4. New instance created (does NOT replace current). Endpoint differs from production.
5. Verify the restored instance has expected data.
6. **DECIDE**: cutover strategy. Options:
   - (a) Update `DATABASE_URL` Cloudflare secret to new instance, deploy, decommission old (downtime ~5 min)
   - (b) Use AWS RDS rename trick (rename old to `_old`, rename new to production name, update DNS) — minimal downtime
   - (c) Read-only mode on app while migrating data
   - Default suggestion at MVP: (a). Rare event; downtime acceptable.
7. Decommission the old instance (or keep for forensics, depending on cause).

### Postgres — snapshot restore

When: full disaster, loss of instance.

1. From RDS console: select snapshot → "Restore snapshot".
2. New instance provisioned from snapshot.
3. Same cutover steps as above.

### S3 — versioned restore

When: file deleted or corrupted.

```bash
aws s3api list-object-versions --bucket <bucket> --prefix <key>
# Identify the version-id of the good version
aws s3api copy-object --copy-source <bucket>/<key>?versionId=<version-id> --bucket <bucket> --key <key>
```

For mass restore, write a script. **FILL IN** when needed.

### Code / config

`git` clone. No special procedure.

---

## Drill cadence

> **DECIDE**: drill cadence. Default suggestion: quarterly. At MVP scale, "annually" is also defensible if reasoned about.

Drill = simulated restore test on a non-production environment. Verifies:
1. Backup actually contains expected data
2. Restore procedure documented here is accurate
3. RTO target is achievable (record actual restore time)
4. Team knows what to do (reduces panic during real incidents)

After each drill:
1. Update this runbook with any corrections.
2. Update RTO target if actual times diverge from goal.
3. Record drill in `SESSION_LOG.md` with date and outcome.

> **FILL IN**: first drill date, planned before pilot launch (per `build-plan.md` Phase 9 acceptance: "DPDP deletion test").

---

## Disaster scenarios — what to do

### Scenario: AWS RDS Mumbai region outage

**Likelihood**: rare but real (region-wide AWS outages happen ~once per year).

**Action**:
1. Cloudflare Workers will return 5xx for any DB-bound endpoint. Cached/static endpoints continue working.
2. Wait for AWS region recovery (typically minutes to hours; AWS publishes status).
3. If outage extends > **DECIDE** hours (suggestion: 4), invoke disaster failover plan below.

> **DECIDE**: disaster failover plan. At MVP scale, options:
> - (a) Wait it out (acceptable for pilot scale)
> - (b) Restore latest snapshot to a different AWS region (loses India residency temporarily; DPDP risk)
> - (c) Migrate to DO Bangalore Postgres temporarily (per ADR-0001 fallback path)
> Default at MVP: (a). Document the decision when scale changes.

### Scenario: Cloudflare account compromise

**Action**:
1. Rotate all Cloudflare-stored secrets immediately (per `secrets-management.md`).
2. Revoke all OpenRouter / Google OAuth / AWS keys.
3. Deploy from a known-good git ref to a new Cloudflare account if needed.
4. Update DNS to point at the new Worker.
5. Forensics: review Cloudflare audit log for unauthorized changes.

### Scenario: Database fully corrupted (very rare)

**Action**: snapshot restore (procedure above). Most recent good snapshot wins. Lose data between snapshot and corruption (hopefully < 1 day with daily snapshots + point-in-time).

---

## Things to revisit

- **Cross-region backup replication** (e.g. snapshot copies to ap-southeast-1) when DPDP comfort allows it AND uptime requirements warrant it.
- **Off-AWS backup** (e.g. periodic `pg_dump` to a different cloud) when single-cloud risk is unacceptable.
- **Automated drill** (a CI job that periodically restores and verifies) when team grows.

---

## Changelog

| Date | Change | Reason |
|---|---|---|
| 2026-04-28 | Initial template. | Backup posture should exist before any production data. |
