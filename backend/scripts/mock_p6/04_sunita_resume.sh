#!/usr/bin/env bash
# =============================================================================
# mock_p6/04_sunita_resume.sh
#
# Resume 04_sunita.sh from exactly where it crashed: S7 exists and brief is
# stored in DB, but notes, MOM, action items, and end_session were never run.
#
# What was already done:
#   S1–S6: complete
#   S7:    session created (971ed01c-...), brief generated — nothing else
#
# What this script does:
#   1. Completes S7: add notes, MOM, items, end
#   2. Runs S8 from scratch
#   3. Appends S_SUNITA_1 and S_SUNITA_8 to IDS_FILE
#
# Run from repo root:  cd backend && bash scripts/mock_p6/04_sunita_resume.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids

source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
cd "$(dirname "$0")/../.."

DB="postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev"

echo "======================================================="
echo "  Sunita Rao — RESUME from S7"
echo "  S7 session and brief already exist in DB."
echo "  Completing S7 then running S8 fresh."
echo "======================================================="

# ── Hardcoded IDs from the failed run ─────────────────────────────────────────
S7="971ed01c-4b14-4d17-be18-a5b02977953e"
AI_S6_SCREEN="c38208b4-41e4-409a-adb9-bc386ff32325"   # "No screens after 10pm..."

# Retrieve S1 from DB (needed for IDS_FILE at the end)
S1=$(psql "$DB" -t -A -c "
  SELECT s.id FROM sessions s
  WHERE s.client_id = '$CLIENT3_ID' AND s.session_number = 1
  LIMIT 1;")

echo ""
echo "══ COMPLETING SESSION 7 (already started) ════════════"
echo "  Session ID: $S7 (existing)"
echo "  Brief:      already in DB — skipping LLM call"
echo ""

# ── S7: add notes ─────────────────────────────────────────────────────────────
NOTES_S7="Blood test results: testosterone elevated (borderline), fasting insulin 18 mIU/L (borderline insulin resistance), Vitamin D 18 ng/mL (deficient), ferritin normal. Results reframe the protocol — insulin resistance is confirmed as the primary driver. Low-GI diet is now essential, not optional. Vitamin D supplement started (60,000 IU weekly sachet). Work stress returning — new campaign starting. Screen cutoff still failing — Sunita admitted scrolling until 11pm."

add_notes "$S7" "$NOTES_S7"
echo "  ✓ Notes added to S7"

# ── S7: generate MOM ──────────────────────────────────────────────────────────
echo "  Generating MOM draft for S7 (LLM)..."
MOM7=$(generate_mom_draft "$S7" "$NOTES_S7")
print_mom_draft "Sunita — Session 7" "$MOM7"
DRAFT7=$(echo "$MOM7" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL7="$DRAFT7

Coach note: Insulin resistance confirmed. This is a turning point — we now have objective data to work with. Low-GI is no longer a suggestion; it is the primary therapeutic intervention.

The screen cutoff has now been discussed in S3, S4, and S7 — it keeps failing because of external triggers (work, husband watching TV). This is a household systems problem, not a willpower problem. Blue light glasses are the right solution. Source them before S8.

Vitamin D at 18 ng/mL is significant for PCOD — it directly affects testosterone and insulin sensitivity. The supplement protocol will take 8–12 weeks to normalise. Track Vitamin D on next blood test."

patch_mom_final "$S7" "$FINAL7"
send_mom "$S7"

verify_hint "S7 MOM sent" \
  "DB: psql \$DB -c \"SELECT llm_call_id IS NOT NULL AS llm_used, final_text != draft_text AS hc_edited, sent_at IS NOT NULL AS sent FROM moms WHERE session_id = '$S7';\"" \
  "Design: insulin resistance is now in session_notes. S8 brief will draw this context."

# ── S7: action items ──────────────────────────────────────────────────────────
AI_S12=$(create_item "$CLIENT3_ID" "$S7" "Strict low-GI diet for 4 weeks: no white rice, maida, potato — switch to millets, oats, brown rice" "$(date_weeks_from_now 1)")
AI_S13=$(create_item "$CLIENT3_ID" "$S7" "Daily 20-min walk + 2 yoga sessions per week — insulin sensitivity protocol" "$(date_weeks_from_now 1)")
AI_S14=$(create_item "$CLIENT3_ID" "$S7" "Buy blue light glasses and use every evening — structural fix for screen cutoff failure" "$(date_weeks_from_now 1)")

# Screen cutoff item remains a recurring miss in history
mark_item "$AI_S6_SCREEN" "missed"

verify_hint "S7 — insulin resistance now in session notes (critical for S8 brief)" \
  "DB: psql \$DB -c \"SELECT left(session_notes, 200) FROM sessions WHERE id = '$S7';\"" \
  "DB: psql \$DB -c \"SELECT description, status FROM action_items WHERE client_id = '$CLIENT3_ID' AND status = 'missed' ORDER BY created_at;\"" \
  "Design: session_notes for S7 contains 'insulin resistance confirmed'. S8 brief should reference this." \
  "Design: Screen cutoff now has 2 missed entries. S8 brief must call it a 'recurring' issue."

end_session "$S7"
echo "  ✓ Session 7 complete."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 8  (today — THE REAL TEST)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 8 — THE REAL TEST ════════════════════════"
echo "  7 sessions of real PCOD context now in DB."
echo "  Brief should be the richest output of the entire mock test."
echo ""

S8=$(create_session "$CLIENT3_ID" 8 "$(today_iso)")
echo "  Session ID: $S8"
print_ast_summary "Sunita before S8" "$CLIENT3_ID"

echo "  Generating brief for S8 (LLM)..."
B8=$(generate_brief "$S8")
print_brief "Sunita — Session 8 (7 sessions of real context)" "$B8"

verify_hint "S8 brief — THE FULL CONTEXT FARM VERIFICATION" \
  "DB: psql \$DB -c \"SELECT s.session_number, lc.input_tokens FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id JOIN sessions s ON s.id = b.session_id WHERE s.client_id = '$CLIENT3_ID' ORDER BY s.session_number;\"" \
  "Design: MUST see growing input_tokens S1→S8. Flat = context not accumulating." \
  "DB: psql \$DB -c \"SELECT COUNT(*) AS total_snippets FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';\"" \
  "Design: By S8, total snippets should be ≥ 5." \
  "Frontend: http://localhost:3000/clients/$CLIENT3_ID/sessions/$S8  →  open the session page, check brief tab"

echo "  ─── EVALUATE SESSION 8 BRIEF ──────────────────────"
echo "  □  References insulin resistance / blood test findings from S7?"
echo "  □  Flags screen cutoff as a RECURRING miss (failed S3, S4, S7)?"
echo "  □  Mentions the low-GI protocol as the primary current intervention?"
echo "  □  Shows the cycle trend (50d → 38 → 33 → 30)?"
echo "  □  Surfaces tea reduction as a long-running open item?"
echo "  □  Reads like a genuine coaching prep note, not a generic list?"
echo "  ────────────────────────────────────────────────────"
echo ""

NOTES_S8="Sunita bought blue light glasses — using every evening. Screen cutoff now 10:30pm (improvement from 11pm). Low-GI compliance: 11/14 days (3 slips — office birthday cake twice, one dinner party). Walk + yoga: 13/14 walks, 4 yoga sessions. Weight 65.8kg (-2.2kg total from baseline). Period came at day 27 — closest to a normal cycle in 3 years. She cried briefly when she told me. Ferritin improved. Vitamin D improving. Testosterone still elevated but trending down. Tea now at 1–2 cups — solved quietly."

add_notes "$S8" "$NOTES_S8"

echo "  Generating MOM draft for S8 (LLM)..."
MOM8=$(generate_mom_draft "$S8" "$NOTES_S8")
print_mom_draft "Sunita — Session 8" "$MOM8"

DRAFT8=$(echo "$MOM8" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL8="$DRAFT8

Coach note: The 27-day cycle is the most significant result of 8 sessions. This is what lifestyle intervention looks like when it works. Acknowledge this fully with Sunita — she needs to internalise this as her own achievement, not something the protocol did to her.

The screen cutoff is now being solved structurally (blue light glasses + earlier stop). The 10:30pm time is progress but 10pm is the target — 30 more minutes to close.

Tea quietly dropped to 1–2 cups without being an action item in the last 2 sessions. This is what sustainable habit change looks like.

Priority for M009:
1. Low-GI: target 13+/14 days (social exceptions are fine, planning for them is the skill)
2. Screen cutoff: 10pm is the goal (from 10:30pm)
3. Testosterone repeat test at M010 — 12 weeks of low-GI should show measurable change"

patch_mom_final "$S8" "$FINAL8"
send_mom "$S8"

verify_hint "S8 MOM — final snippet count and style injection check" \
  "DB: psql \$DB -c \"SELECT lc.snippet_count, lc.snippet_tokens, lc.input_tokens FROM llm_calls lc JOIN moms m ON m.llm_call_id = lc.id JOIN sessions s ON s.id = m.session_id WHERE s.id = '$S8' AND lc.use_case = 'mom_generation';\"" \
  "Design: snippet_count ≥ 1 means the style flywheel is injecting learned HC voice into MOM drafts." \
  "Frontend: http://localhost:3000/clients/$CLIENT3_ID/sessions/$S8  →  MOM tab, compare draft vs sent"

AI_S15=$(create_item "$CLIENT3_ID" "$S8" "Low-GI: target 13+/14 days — plan social exceptions in advance rather than avoiding them" "$(date_weeks_from_now 2)")
AI_S16=$(create_item "$CLIENT3_ID" "$S8" "Move screen cutoff from 10:30pm to 10pm — 30-minute further improvement" "$(date_weeks_from_now 2)")

end_session "$S8"
echo "  ✓ Session 8 done."

cat >> "$IDS_FILE" <<EOF
S_SUNITA_1=$S1
S_SUNITA_8=$S8
EOF

echo ""
echo "======================================================="
echo "  Sunita resume complete. S7 finished, S8 done."
echo "  Next: bash scripts/mock_p6/05_verify_flywheel.sh"
echo "======================================================="
