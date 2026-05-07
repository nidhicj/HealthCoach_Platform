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

echo "======================================================="
echo "  Maya Patel — Onboarding Client"
echo "======================================================="

# ─────────────────────────────────────────────────────────────────────────────
# M000 — Onboarding session (no LLM)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "── M000: Onboarding session ─────────────────────────"

S_MAYA_0=$(create_session "$CLIENT1_ID" 0 "$(weeks_ago 2)")
echo "  Session ID: $S_MAYA_0"

add_notes "$S_MAYA_0" "Onboarding session. Maya is 29, software engineer, works from home. Main complaints: difficulty waking before 9am, irregular sleep (midnight to 9am), no structured morning. Goals: wake by 7am, build a 30-minute morning practice over 8 weeks."

# M000 uses a template brief (no LLM call) — just confirm it returns
BRIEF_M000=$(_get "/api/sessions/$S_MAYA_0/brief")
echo "$BRIEF_M000" | python3 -c "
import sys, json
b = json.load(sys.stdin)
print('  ✓ M000 brief returned (template — no LLM):')
print('   ', b.get('brief_text','')[:100], '...')
"

# Manual MOM — onboarding note, no AI needed
_post "/api/sessions/$S_MAYA_0/mom" '{
  "draft_text": "Onboarding complete. Baseline established: sleep midnight–9am, no morning routine, WFH.\n\nGoal: 7am wake-up + 30-min morning practice in 8 weeks.\n\nNo action items this session. M001 will set first commitments."
}' > /dev/null

send_mom "$S_MAYA_0"
end_session "$S_MAYA_0"
echo "  ✓ M000 ended. No action items seeded."

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

AI_MAYA_1=$(create_item "$CLIENT1_ID" "$S_MAYA_1" \
  "Move phone charger to kitchen — end the reach-for-phone habit on waking" \
  "$(date_weeks_from_now 1)")

AI_MAYA_2=$(create_item "$CLIENT1_ID" "$S_MAYA_1" \
  "Run the 3-step launch sequence every morning: water → 10-min walk → journal" \
  "$(date_weeks_from_now 2)")

end_session "$S_MAYA_1"
echo "  ✓ M001 complete. 2 action items created."

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
