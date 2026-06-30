# PHASE-11: Client Profile and Health Metrics

**Unit**: Unit_001_HcCoreCycle
**Status**: Draft
**Verification date**: TBD
**Implements**: SPEC-0001 (client data depth — new backend + DB + frontend)
**ADRs implemented**: None — JSONB chosen over separate tables; decision embedded in §3.

---

## 0. Prerequisites

Anthem rules from CLAUDE.md apply. Preflight every substantive response per PREFLIGHT.md. Builds on top of PHASE-10; branch `feature/unit-001-phase-11-client-profile-and-health-metrics` cut from `main` (post P10 merge).

---

## 1. Scope

Two capabilities added to the client detail page:

1. **Client Profile (demographics):** A gear icon in the client header opens a shadcn `<Sheet>` slide-over. HC fills in optional demographic fields. Only non-empty fields render in the Details card.

2. **Health Metrics:** HC defines custom metrics per client (name, value, unit). Up to 3 can be flagged for display on the roster card. A new Health Metrics card appears on the client detail page (70% of the goal-row width; Goal card shrinks to 30%). Metrics are edited inline with Save/Edit freeze pattern.

**Not in scope for P11:**
- Blood test upload / PDF parsing → metric extraction (flagged as future enhancement, see §6)
- Health metric time series / trend charts
- Metric aggregation across clients

---

## 2. Data model

### 2.1 Strategy

Add two JSONB columns to the existing `clients` table. No new tables. One migration.

**Why JSONB over separate tables:**
- Demographics fields are sparse (all optional) — JSONB avoids a table with 8 nullable columns and a forced JOIN on every client fetch.
- Health metrics are user-defined (custom names) — schema-less storage is appropriate.
- P11 never queries or aggregates on individual metric values — no index benefit to columns.
- If time-series is added later (future phase), a proper `health_readings` table will be created then; JSONB stores current-value snapshot only.

### 2.2 `demographics` column

```sql
ALTER TABLE clients ADD COLUMN IF NOT EXISTS demographics JSONB DEFAULT NULL;
```

Shape (all fields optional):
```json
{
  "dob": "1990-04-12",
  "gender": "female",
  "city": "Bengaluru",
  "occupation": "Software engineer",
  "medical_conditions": "Type 2 diabetes, hypothyroidism",
  "allergies": "Penicillin",
  "current_medications": "Metformin 500mg",
  "emergency_contact": "Rahul Sharma +91 98765 43210"
}
```

### 2.3 `health_metrics` column

```sql
ALTER TABLE clients ADD COLUMN IF NOT EXISTS health_metrics JSONB DEFAULT '[]'::jsonb;
```

Shape (array of metric objects):
```json
[
  { "id": "uuid-v4", "name": "Weight", "value": "72", "unit": "kg", "display_on_card": true },
  { "id": "uuid-v4", "name": "HbA1c", "value": "6.2", "unit": "%", "display_on_card": true },
  { "id": "uuid-v4", "name": "Fasting glucose", "value": "98", "unit": "mg/dL", "display_on_card": false }
]
```

- `id`: client-generated UUIDv4 (frontend generates on add)
- `display_on_card`: max 3 can be `true` — enforced in frontend + backend validator
- No ordering beyond array position

---

## 3. Backend changes

### 3.1 Migration

File: `backend/src/db/migrations/0007_client_demographics_and_health_metrics.sql`

```sql
ALTER TABLE clients ADD COLUMN IF NOT EXISTS demographics JSONB DEFAULT NULL;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS health_metrics JSONB DEFAULT '[]'::jsonb;
```

(Adjust migration number to follow the latest existing migration.)

### 3.2 `ClientOut` / `ClientDetailOut` schema

Add to `ClientOut`:
```python
demographics: dict | None = None
health_metrics: list[dict] = []
```

### 3.3 `PatchClientInput` extension

Add to the existing `PatchClientInput` model:
```python
demographics: dict | None = None
health_metrics: list[dict] | None = None

@field_validator("health_metrics")
@classmethod
def validate_health_metrics(cls, v: list[dict] | None) -> list[dict] | None:
    if v is None:
        return v
    display_count = sum(1 for m in v if m.get("display_on_card"))
    if display_count > 3:
        raise ValueError("At most 3 metrics can have display_on_card=true")
    return v
```

Patch handler update — add after the `journey_stage` block:
```python
if body.demographics is not None:
    client.demographics = body.demographics
if body.health_metrics is not None:
    client.health_metrics = body.health_metrics
```

### 3.4 `ClientCreate` extension

Add optional fields to `ClientCreate` (both default None / []):
```python
demographics: dict | None = None
health_metrics: list[dict] = []
```

Pass through in the POST route create call.

---

## 4. Frontend changes

### 4.1 API wrapper (`frontend/src/lib/api/clients.ts`)

- Extend `ClientOutSchema` Zod schema:
  ```typescript
  demographics: z.record(z.string()).nullable().optional(),
  health_metrics: z.array(z.object({
    id: z.string(),
    name: z.string(),
    value: z.string(),
    unit: z.string(),
    display_on_card: z.boolean(),
  })).default([]),
  ```
- Extend `patchClient` input type:
  ```typescript
  input: {
    journey_stage?: string;
    demographics?: Record<string, string> | null;
    health_metrics?: Array<{ id: string; name: string; value: string; unit: string; display_on_card: boolean }>;
  }
  ```

### 4.2 Client detail page layout change

File: `frontend/src/app/(app)/clients/[clientId]/page.tsx`

**Goal row** (currently full-width `bg-section-fill-03`): split into 30/70:
```tsx
<div className="flex gap-4">
  {/* Goal card — 30% */}
  <section className="w-[30%] rounded-2xl border border-border bg-section-fill-03 p-6">
    ...existing goal content...
  </section>

  {/* Health Metrics card — 70% */}
  <section className="flex-1 rounded-2xl border border-border bg-section-fill-01 p-6">
    <HealthMetricsCard ... />
  </section>
</div>
```

### 4.3 Gear icon → demographics sheet

In the client header area (top right, same level as client name):
```tsx
import { Settings } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

<Sheet>
  <SheetTrigger asChild>
    <button className="rounded-md p-1 text-muted-foreground hover:text-foreground transition-colors">
      <Settings size={18} />
    </button>
  </SheetTrigger>
  <SheetContent side="right" className="w-[420px] overflow-y-auto">
    <SheetHeader>
      <SheetTitle>Client profile</SheetTitle>
    </SheetHeader>
    <DemographicsForm client={client} onSave={handleDemoSave} />
  </SheetContent>
</Sheet>
```

`DemographicsForm` fields (all optional):
| Field | Input type | Key |
|-------|-----------|-----|
| Date of birth | `<input type="date">` | `dob` |
| Gender | `<select>` (Female / Male / Non-binary / Prefer not to say) | `gender` |
| City / location | text | `city` |
| Occupation | text | `occupation` |
| Medical conditions | `<textarea>` | `medical_conditions` |
| Allergies | `<textarea>` | `allergies` |
| Current medications | `<textarea>` | `current_medications` |
| Emergency contact | text | `emergency_contact` |

On Save: `patchClient(clientId, { demographics: formValues })` → update `client` state → sheet closes.

### 4.4 Details card — show only non-empty demographics

The Details card (bottom-right, `bg-section-fill-02`) currently shows email, phone, stage, since. Add demographics fields below, rendered only if non-null/non-empty:

```tsx
{client.demographics?.dob && (
  <DetailRow label="Date of birth" value={client.demographics.dob} />
)}
{client.demographics?.gender && (
  <DetailRow label="Gender" value={client.demographics.gender} />
)}
// ...repeat for each field
```

### 4.5 Health Metrics card (`HealthMetricsCard` component)

New component: `frontend/src/components/health-metrics-card.tsx`

Props:
```typescript
interface HealthMetricsCardProps {
  clientId: string;
  metrics: HealthMetric[];
  onSave: (metrics: HealthMetric[]) => void;
}
```

Behaviour:
- **View mode (frozen):** list of metrics as `Name: Value Unit` rows; Edit button top-right.
- **Edit mode (unfrozen):** each metric row shows name/value/unit inputs + a `display_on_card` checkbox (labelled "Show on roster"). Add metric button (+) at bottom. Remove button (×) per row. Save button top-right calls `patchClient(clientId, { health_metrics: metrics })`.
- **Constraint:** checkbox disables when 3 are already selected (unless this metric is already one of the 3).
- **Empty state:** "No metrics yet. Click Edit to add." (Fraunces italic style)
- Uses `crypto.randomUUID()` to generate `id` on new metric add.

### 4.6 Roster card — display up to 3 flagged metrics

File: `frontend/src/components/client-card.tsx`

Add `metrics` prop:
```typescript
metrics?: Array<{ name: string; value: string; unit: string }>;
```

Below the stage badge, render:
```tsx
{metrics && metrics.length > 0 && (
  <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
    {metrics.map(m => (
      <span key={m.name} className="text-xs text-muted-foreground">
        {m.name}: <span className="font-medium text-foreground">{m.value} {m.unit}</span>
      </span>
    ))}
  </div>
)}
```

In `dashboard/page.tsx`, pass `metrics={client.health_metrics.filter(m => m.display_on_card)}` to each `<ClientCard>`.

---

## 5. Deliverables checklist

- [ ] Migration file committed and auto-applied on startup (same Dockerfile entrypoint pattern as existing migrations)
- [ ] `ClientOut` Zod schema + Python model updated
- [ ] `patchClient` API wrapper updated (demographics + health_metrics)
- [ ] Gear icon + Sheet in client header
- [ ] `DemographicsForm` — all 8 fields, all optional, Save calls PATCH
- [ ] Details card shows only non-empty demographic fields
- [ ] Goal row split 30/70 with HealthMetricsCard
- [ ] `HealthMetricsCard` component — view/edit mode, constraint enforced, Save/Edit freeze pattern
- [ ] Roster card shows up to 3 flagged metrics
- [ ] Typecheck passes; backend tests pass (no regressions)

---

## 6. Future enhancement (not P11)

**Blood test → health metrics (plus feature):**
HC uploads a PDF/image/DOCX blood test report. Backend (or an LLM call) extracts metric names and values. HC reviews and confirms before saving to `health_metrics`. This would reuse the existing `health_metrics` JSONB structure — no schema change needed, just a new extraction endpoint.

Tracked here for awareness; not scheduled.

---

## 7. Session log

| Date | Event |
|------|-------|
| 2026-06-30 | Phase scoped, spec drafted. Design confirmed by SoJo. Branch cut. |
