# ADR-0007: App-layer Fernet encryption for the `demographics` column

**Status**: Accepted
**Date**: 2026-06-30
**Decision driver**: SoJo
**Supersedes**: n/a
**Relates to**: ADR-0005 (auth strategy), ADR-0006 (observability), PHASE-11 spec

---

## Context

Phase 11 adds a `demographics` JSONB column to the `clients` table. The column stores eight optional
fields, three of which are sensitive health PII:

- `medical_conditions` — chronic diagnoses (e.g. "Type 2 diabetes, hypothyroidism")
- `allergies` — drug/food allergies
- `current_medications` — active prescriptions with dosages

CLAUDE.md §9.5 requires: *"PII and session content are encrypted at rest and in logs. Structured PII
fields are encrypted column-level where the chosen DB supports it."*

The DPDP Act 2023 §8(4) mandates reasonable security safeguards for personal data. While DPDP does
not create a separate "sensitive personal data" category (as GDPR does), health data is high-risk in
practice and its unauthorised disclosure can cause significant harm to the data principal.

This decision was reached because Phase 11 was already in review when the gap was flagged; the column
had not yet been deployed to production, making it the right moment to fix before data lands in plain
text.

### Forces at play

- **Compliance**: plain JSONB violates CLAUDE.md §9.5 and DPDP reasonable-security expectation.
- **DB portability**: solution must work identically on local Postgres and Supabase without extensions.
- **Queryability**: demographics fields are **never** filtered, sorted, or joined on — only read whole
  and written whole. Losing JSONB operators is acceptable.
- **Transparency**: encryption logic should not scatter across every endpoint that reads or writes the
  column.
- **Key management**: keep it simple until volume justifies a KMS.

---

## Decision

Encrypt the `demographics` field with **app-layer Fernet (AES-128-CBC + HMAC-SHA256)** via a
SQLAlchemy `TypeDecorator`. The `Client.demographics` ORM column changes from `JSONB` to `Text`
(stores Fernet ciphertext as URL-safe base64). The Python/Pydantic layer continues to see
`dict[str, str] | None` — encryption and decryption are transparent at the ORM boundary.

**Key**: a 32-byte URL-safe base64 key (`Fernet.generate_key()`) stored in `DEMOGRAPHICS_ENCRYPTION_KEY`
env var. Rotated manually; rotation requires a one-off migration script to re-encrypt rows.

**Column change**: the P11 Alembic migration (`a1b2c3d4e5f6`) is updated *before merge* to add
`demographics` as `TEXT` instead of `JSONB`. No prod rows exist yet, so no data migration is needed.

**`health_metrics`** is not encrypted in this ADR (see §Consequences / Things to revisit).

---

## Rationale

1. **TypeDecorator keeps encryption transparent**: no endpoint code changes. The ORM intercepts
   `process_bind_param` (Python dict → encrypt → base64 string) and `process_result_value`
   (base64 string → decrypt → Python dict). All existing read/write paths work unchanged.

2. **Fernet over pgcrypto**: pgcrypto requires the `pgcrypto` extension and embeds the encryption key
   inside SQL queries, exposing it in query logs. Fernet keeps the key in env vars and out of the DB
   connection entirely. Works on any Postgres host including Supabase without extension configuration.

3. **App-layer over column-level DB encryption** (e.g. TDE): transparent data encryption at the
   storage layer protects against disk theft but not against a compromised DB user — the most likely
   threat model. App-layer encryption protects even if someone gets a DB dump.

4. **HMAC authentication**: Fernet tokens include an HMAC over the ciphertext. Tampered ciphertext
   raises `InvalidToken` on decrypt, providing integrity as well as confidentiality.

5. **Deferred KMS**: Fernet + env var is the correct minimum for a pre-Series A India healthtech.
   Migrating to AWS KMS / GCP KMS later requires only swapping the `TypeDecorator`'s encrypt/decrypt
   calls, not any schema or endpoint change.

---

## Consequences

### Positive
- `demographics` PII encrypted at rest; a DB dump exposes only ciphertext.
- CLAUDE.md §9.5 and DPDP reasonable-security expectation satisfied for this column.
- Zero endpoint code changes — encryption is fully at the ORM layer.
- Integrity protection via Fernet HMAC.

### Negative / tradeoffs accepted
- `demographics` JSONB operator queries (e.g. `->`, `@>`) become impossible. **Accepted**: no
  current or planned query uses them.
- Key rotation requires a one-off script to decrypt and re-encrypt all rows. **Accepted**: acceptable
  operational overhead at current scale; documented as a runbook item.
- If `DEMOGRAPHICS_ENCRYPTION_KEY` is lost, demographics data is permanently unreadable. **Mitigated**:
  key backed up in the same secrets store as DB credentials; standard operational discipline.

### Things to revisit
- **`health_metrics` encryption**: also contains sensitive data (blood markers, biometrics). Deferred
  because health_metrics are user-defined and queried by `display_on_card` (array scan) — encryption
  would break that filter. Re-evaluate if filtering moves server-side: current filter is client-side
  in the frontend.
- **KMS**: when the platform passes any Indian regulatory audit or processes >10,000 data principals,
  migrate to a managed KMS so key material never touches application memory as a plain string.
- **Audit log of demographics access**: currently no access log for who read a client's demographics.
  Add when DPDP grievance-officer requirement kicks in.

---

## Options considered

### Option 1 — SQLAlchemy TypeDecorator + Fernet (chosen)
App-layer encryption, transparent to endpoints, no DB extension required.

### Option 2 — pgcrypto column encryption
Key embedded in SQL queries → appears in query logs. Requires Supabase extension. Not chosen.

### Option 3 — Defer to P12 with documented gap
Compliant workaround on paper (ADR + timeline), but leaves plain-text health data in prod DB.
Not acceptable given the data sensitivity and the fact that the column is new and undeployed.

### Option 4 — Store non-sensitive fields only (drop medical_conditions, allergies, medications)
Avoids the problem but removes coach-facing functionality SoJo explicitly requested. Not chosen.

---

## References

- CLAUDE.md §9.5 — encrypted at rest requirement
- CLAUDE.md §10 — DPDP compliance summary
- DPDP Act 2023 §8(4) — reasonable security safeguards
- Python `cryptography` library — Fernet spec: https://cryptography.io/en/latest/fernet/
- `docs/specs/Unit_001_HcCoreCycle/PHASE-11-client-profile-and-health-metrics.md` §2.2

---

## Changelog

| Date | Change | Reason |
|------|--------|--------|
| 2026-06-30 | Initial draft, Accepted. | Phase 11 review flagged plain-text health PII before prod deploy. |
