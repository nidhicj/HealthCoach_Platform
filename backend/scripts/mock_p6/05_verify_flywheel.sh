#!/usr/bin/env bash
# =============================================================================
# mock_p6/05_verify_flywheel.sh
# Verifies the style flywheel:
#   1. How many style snippets were captured across all sessions?
#   2. For the most recent MOM draft per client, was snippet_count > 0?
#   3. Prints a full summary of all LLM calls made in this mock test.
#
# No LLM calls — pure DB inspection.
#
# Run from repo root:  cd backend && bash scripts/mock_p6/05_verify_flywheel.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids

source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
cd "$(dirname "$0")/../.."

DB="postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev"

echo "======================================================="
echo "  P6 Mock Test — Stage 5: Flywheel Verification"
echo "======================================================="

python3 - <<PYEOF
import psycopg2

hc_id    = "$HC_ID"
c1       = "$CLIENT1_ID"
c2       = "$CLIENT2_ID"
c3       = "$CLIENT3_ID"

conn = psycopg2.connect("$DB")
cur  = conn.cursor()

# ── Style snippets ────────────────────────────────────────────────────────────
print()
print("── Style snippets ──────────────────────────────────")
cur.execute("""
    SELECT snippet_type, created_at::date,
           left(hc_modified_text, 90) AS preview
    FROM hc_style_snippets
    WHERE hc_user_id = %s
    ORDER BY created_at
""", (hc_id,))
rows = cur.fetchall()
print(f"  Total captured: {len(rows)}")
print()
for i, (stype, dt, preview) in enumerate(rows, 1):
    print(f"  [{i}] {dt}  type={stype}")
    print(f"      {preview!r}")
    print()

# ── LLM calls per use-case ────────────────────────────────────────────────────
print("── LLM calls breakdown ─────────────────────────────")
cur.execute("""
    SELECT use_case, COUNT(*) AS n,
           SUM(input_tokens)  AS in_tokens,
           SUM(output_tokens) AS out_tokens,
           ROUND(AVG(latency_ms))  AS avg_latency_ms
    FROM llm_calls
    WHERE hc_user_id = %s
    GROUP BY use_case
    ORDER BY use_case
""", (hc_id,))
for use_case, n, in_tok, out_tok, avg_lat in cur.fetchall():
    print(f"  {use_case:<22}  calls={n}  in_tokens={in_tok}  out_tokens={out_tok}  avg_latency={avg_lat}ms")

# ── Snippet injection — most recent MOM per client ────────────────────────────
print()
print("── Snippet injection in latest MOM drafts ──────────")
for label, cid in [("Maya", c1), ("Ravi", c2), ("Sunita", c3)]:
    cur.execute("""
        SELECT lc.snippet_count, lc.snippet_tokens, lc.created_at::date
        FROM llm_calls lc
        JOIN moms m ON m.llm_call_id = lc.id
        JOIN sessions s ON s.id = m.session_id
        WHERE s.client_id = %s AND lc.use_case = 'mom_generation'
        ORDER BY lc.created_at DESC
        LIMIT 1
    """, (cid,))
    row = cur.fetchone()
    if row:
        sc, st, dt = row
        mark = "✓" if (sc or 0) >= 1 else "✗"
        print(f"  {mark}  {label:<8} latest MOM draft: snippet_count={sc}, snippet_tokens={st} ({dt})")
    else:
        print(f"  ✗  {label:<8} no MOM LLM call found")

# ── Brief progression — input tokens grew as context grew ────────────────────
print()
print("── Brief prompt size progression (tokens) ──────────")
for label, cid in [("Maya", c1), ("Ravi", c2), ("Sunita", c3)]:
    cur.execute("""
        SELECT s.session_number, lc.input_tokens
        FROM llm_calls lc
        JOIN session_briefs b ON b.llm_call_id = lc.id
        JOIN sessions s ON s.id = b.session_id
        WHERE s.client_id = %s AND lc.use_case = 'brief_generation'
        ORDER BY s.session_number
    """, (cid,))
    rows = cur.fetchall()
    if rows:
        progression = "  →  ".join(f"S{sn}:{tok}" for sn, tok in rows)
        print(f"  {label:<8} {progression}")
    else:
        print(f"  {label:<8} no brief LLM calls found")

# ── Token totals ──────────────────────────────────────────────────────────────
print()
print("── Token totals ────────────────────────────────────")
cur.execute("""
    SELECT SUM(input_tokens), SUM(output_tokens)
    FROM llm_calls WHERE hc_user_id = %s
""", (hc_id,))
in_total, out_total = cur.fetchone()
print(f"  Input tokens  : {in_total:,}")
print(f"  Output tokens : {out_total:,}")
print(f"  Total tokens  : {(in_total or 0) + (out_total or 0):,}")

cur.close()
conn.close()
PYEOF

echo ""
echo "======================================================="
echo "  FINAL EVALUATION CHECKLIST"
echo ""
echo "  Context tracking:"
echo "  □  Ravi S1 brief: sparse — no items, no history?"
echo "  □  Ravi S5 brief: names open items, flags missed strength?"
echo "  □  Sunita S1 brief: sparse — new client?"
echo "  □  Sunita S8 brief: insulin resistance, recurring screen miss,"
echo "       low-GI protocol, 7-session cycle trend visible?"
echo "  □  Brief input token count GREW across sessions for Ravi/Sunita?"
echo "       (this is the context farm — more tokens = more context injected)"
echo ""
echo "  Style learning:"
echo "  □  Style snippets captured ≥ 5 total?"
echo "  □  snippet_count ≥ 1 in latest MOM drafts for Ravi and Sunita?"
echo ""
echo "  Quality:"
echo "  □  No hallucinated facts in any brief or MOM?"
echo "  □  MOMs are structured (summary, discussion, actions) not generic?"
echo "  □  Sunita's MOM drafts reference PCOD context specifically?"
echo "  □  Ravi's later MOM drafts feel more like the HC's voice?"
echo "======================================================="
