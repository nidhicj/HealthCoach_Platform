#!/usr/bin/env bash
# =============================================================================
# mock_p6/02_maya.sh
# Maya Patel — onboarding client, 2 sessions.
#
# Flow:
#   M000 — onboarding session (no LLM brief, manual MOM, no action items)
#   M001 — first real session
#           brief is generated BEFORE notes are added
#           → expected: sparse, acknowledges zero history
#           notes added, MOM drafted by AI, HC edits, sent
#
# LLM calls: 1 brief + 1 MOM = 2 calls
#
# Run from repo root:  cd backend && bash scripts/mock_p6/02_maya.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids
DB="postgresql://postgres:localdevpassword@localhost:5432/tapas_dev"

echo "======================================================="
echo "  Maya Patel — Onboarding Client"
echo "======================================================="

# ─────────────────────────────────────────────────────────────────────────────
# M000 — already completed manually earlier this run (session/brief/MOM/freeze/
# end all done before this script was patched) — S_MAYA_0 comes from require_ids.
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "── M000: already completed, skipping ────────────────"
echo "  Session ID: $S_MAYA_0"

# ─────────────────────────────────────────────────────────────────────────────
# M001 — First real session
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "── M001: First real session ─────────────────────────"

S_MAYA_1=$(create_session "$CLIENT1_ID" 1 "$(today_iso)")
echo "  Session ID: $S_MAYA_1"

# Check AST before generating brief
print_ast_summary "Maya before M001" "$CLIENT1_ID"

# Generate brief BEFORE adding any notes
echo "  Generating brief (LLM call)..."
BRIEF_M001=$(generate_brief "$S_MAYA_1")
print_brief "Maya — M001 (zero history)" "$BRIEF_M001"

verify_hint "M001 LLM brief — zero-history baseline" \
  "DB:       psql \$DB -c \"SELECT lc.input_tokens, lc.output_tokens, lc.model_served, lc.latency_ms FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id WHERE b.session_id = '$S_MAYA_1';\"" \
  "Design:   input_tokens here is the BASELINE — no prior history injected (no open items, no past sessions)." \
  "Design:   For Ravi S5 and Sunita S8, input_tokens will be much larger. That growth IS the context farm." \
  "Design:   The brief text must NOT invent goals or history. It should say 'first session after onboarding'."

echo "  EVALUATE: Brief should acknowledge no action items and no history."
echo "  It should NOT invent goals or history. It should orient to a first session."
echo ""

# Now run the session
NOTES_M001="First real session after onboarding. Maya woke at 6:45am today — rare win. Discussed the 'launch sequence' concept: phone off for first 30 min, glass of water, 10-min walk to the park and back, then journal for 5 min. She lit up at the simplicity. Main friction: phone is her alarm, she reaches for it automatically. Plan: move charger to kitchen tonight."

add_notes "$S_MAYA_1" "$NOTES_M001"

echo "  Generating MOM draft (LLM call)..."
MOM_M001=$(generate_mom_draft "$S_MAYA_1" "$NOTES_M001")
print_mom_draft "Maya — M001" "$MOM_M001"

DRAFT_M001=$(echo "$MOM_M001" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

# HC edits — adds a coach framing note
FINAL_M001="$DRAFT_M001

Coach note: Maya is building a new identity — 'I am a morning person.' Reinforce this framing at the start of every session. The phone-as-alarm is the main structural friction to solve. If she moves it tonight, this habit has a real chance."

patch_mom_final "$S_MAYA_1" "$FINAL_M001"
send_mom "$S_MAYA_1"

verify_hint "M001 MOM — LLM draft saved, HC edited, sent" \
  "DB:       psql \$DB -c \"SELECT llm_call_id IS NOT NULL AS llm_used, draft_text != final_text AS hc_edited, sent_at IS NOT NULL AS sent FROM moms WHERE session_id = '$S_MAYA_1';\"" \
  "DB:       psql \$DB -c \"SELECT snippet_type, left(hc_modified_text,80) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';\"" \
  "Design:   llm_used=true, hc_edited=true, sent=true — all three must be true." \
  "Design:   hc_edited=true triggers style snippet capture. Expect 1 snippet row in hc_style_snippets." \
  "Design:   If no snippet: check moms.llm_call_id is set AND final_text != draft_text in the DB."

AI_MAYA_1=$(create_item "$CLIENT1_ID" "$S_MAYA_1" \
  "Move phone charger to kitchen — end the reach-for-phone habit on waking" \
  "$(date_weeks_from_now 1)")

AI_MAYA_2=$(create_item "$CLIENT1_ID" "$S_MAYA_1" \
  "Run the 3-step launch sequence every morning: water → 10-min walk → journal" \
  "$(date_weeks_from_now 2)")

end_session "$S_MAYA_1"
echo "  ✓ M001 complete. 2 action items created."

verify_hint "M001 action items — these will feed future briefs" \
  "DB:       psql \$DB -c \"SELECT description, due_date, status FROM action_items WHERE session_id = '$S_MAYA_1' ORDER BY created_at;\"" \
  "Frontend: http://localhost:3000/clients/$CLIENT1_ID  →  2 open action items visible on client page" \
  "Design:   These items are now in the AST. If Maya had a session 2, her brief would list both as open items." \
  "Design:   Items are created AFTER the brief is generated — by design. The brief for THIS session saw zero items."

# Save IDs
cat >> "$IDS_FILE" <<EOF
S_MAYA_0=$S_MAYA_0
S_MAYA_1=$S_MAYA_1
AI_MAYA_1=$AI_MAYA_1
AI_MAYA_2=$AI_MAYA_2
EOF

echo ""
echo "======================================================="
echo "  Maya done."
echo "  Next: bash scripts/mock_p6/03_ravi.sh"
echo "======================================================="
