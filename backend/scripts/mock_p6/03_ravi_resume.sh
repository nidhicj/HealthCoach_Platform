#!/usr/bin/env bash
# =============================================================================
# mock_p6/03_ravi_resume.sh
#
# Resume 03_ravi.sh from exactly where it crashed: S5 exists, brief generated,
# notes added — but the MOM draft call hit a transient 503 (KeyError('choices')
# from the LLM provider). Nothing else after that point ran.
#
# What was already done: S1–S4 complete. S5: session created, brief generated,
# notes added — MOM draft, patch, freeze, action items, end_session pending.
#
# Run from repo root:  cd backend && bash scripts/mock_p6/03_ravi_resume.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids

echo "======================================================="
echo "  Ravi Kumar — RESUME from S5"
echo "  S5 session, brief, and notes already exist in DB."
echo "======================================================="

S1="e2c65b89-e943-4d56-b516-374e939342dc"
S2="b260c137-fffb-4634-8146-b0e49ebec556"
S3="0061f433-8765-4ae8-88d0-125c8481b549"
S4="26135a03-6c5a-4f81-893f-b17e75ad7972"
S5="73bb7489-b37a-4aec-9f22-6e3182240451"

echo ""
echo "══ COMPLETING SESSION 5 (already started) ════════════"
echo "  Session ID: $S5 (existing)"
echo "  Brief + notes: already in DB — skipping ahead to MOM draft"
echo ""

NOTES_S5="Ravi hit 2 strength sessions this week — first time meeting the target. Weight 85.2kg (-0.6kg, -2.8kg total). Protein at 76g/day. Weekend plan partially worked: Friday planning done, Saturday stayed on track, Sunday family lunch went over but he recovered by keeping Monday light. He's noticeably more energetic. Wife also started eating healthier — family buy-in now strong. He asked about adding a third strength session. Advised to consolidate 2x first."

echo "  Generating MOM draft for S5 (LLM)..."
MOM5=$(generate_mom_draft "$S5" "$NOTES_S5")
print_mom_draft "Ravi — Session 5" "$MOM5"

DRAFT5=$(echo "$MOM5" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")
FINAL5="$DRAFT5

Coach note: First time hitting the strength target. This is the turning point. Acknowledge it explicitly with Ravi — he needs to own this win.

The family buy-in is a structural advantage now. Don't take it for granted — reinforce it by keeping the household changes visible and celebrated.

Priority for M006: consolidate 2x strength (not 3x yet), close the protein gap to 80g, continue weekend plan."

patch_mom_final "$S5" "$FINAL5"
send_mom "$S5"

AI_R9=$(create_item  "$CLIENT2_ID" "$S5" "Consolidate 2 strength sessions per week before adding a third" "$(date_weeks_from_now 2)")
AI_R10=$(create_item "$CLIENT2_ID" "$S5" "Close protein to 80g/day — one more serving of dal or eggs" "$(date_weeks_from_now 2)")

end_session "$S5"
echo "  ✓ Session 5 done."

cat >> "$IDS_FILE" <<EOF
S_RAVI_1=$S1
S_RAVI_2=$S2
S_RAVI_3=$S3
S_RAVI_4=$S4
S_RAVI_5=$S5
EOF

echo ""
echo "======================================================="
echo "  Ravi resume complete. 5 sessions, 10 LLM calls."
echo "  Next: bash scripts/mock_p6/04_sunita.sh"
echo "======================================================="
