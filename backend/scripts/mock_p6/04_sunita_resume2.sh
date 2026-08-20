#!/usr/bin/env bash
# =============================================================================
# mock_p6/04_sunita_resume2.sh
#
# Resume 04_sunita.sh from exactly where it crashed: S4 exists, brief generated,
# notes added — but the MOM draft call hit a transient 422 ("LLM output failed
# validation"). Nothing else after that point ran.
#
# What was already done: S1–S3 complete. S4: session created, brief generated,
# notes added — MOM draft, patch, freeze, action item, end_session pending.
# Runs S5, S6, S7, S8 fresh after that.
#
# Run from repo root:  cd backend && bash scripts/mock_p6/04_sunita_resume2.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids

echo "======================================================="
echo "  Sunita Rao — RESUME from S4"
echo "  S4 session, brief, and notes already exist in DB."
echo "======================================================="

S1=$(psql "$DB" -t -A -c "SELECT id FROM sessions WHERE client_id = '$CLIENT3_ID' AND session_number = 1;")
AI_S6="53096b6a-e217-4fee-a6d2-e18598981c5a"   # "No screens after 10pm..." — already marked missed
AI_S7="d0cdd53d-048b-4269-bf5b-949fcc8a98d4"   # S4 yoga item — S4 fully completed manually already

echo ""
echo "  S4 already fully completed manually (draft/final/freeze/item/end)."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 5  (9 weeks ago)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 5 ════════════════════════════════════════"

mark_item "$AI_S7" "completed"  # yoga stuck

S5=$(create_session "$CLIENT3_ID" 5 "$(weeks_ago 9)")
echo "  Session ID: $S5"

echo "  Generating brief for S5 (LLM)..."
B5=$(generate_brief "$S5")
print_brief "Sunita — Session 5" "$B5"

NOTES_S5="Yoga: 12/14 days — excellent. Campaign finally over. Energy good. Weight 67.0kg. Iron flagged — fatigue returning despite improved sleep. Sunita skipped meals 3 days during campaign end week. Deadline-related meal skipping is now a clear pattern. Sunday meal prep discussed as a structural fix — prepared food removes decision fatigue during high-stress periods."

add_notes "$S5" "$NOTES_S5"

echo "  Generating MOM draft for S5 (LLM)..."
MOM5=$(generate_mom_draft "$S5" "$NOTES_S5")
print_mom_draft "Sunita — Session 5" "$MOM5"
DRAFT5=$(echo "$MOM5" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL5="$DRAFT5

Coach note: Meal skipping during high-stress periods is now confirmed as a recurring pattern (happened in S3 campaign week and again this week). Sunday meal prep is the correct structural solution — not willpower, not reminders.

Iron and Vitamin D are now the nutritional priorities alongside the anti-inflammatory protocol. These directly affect fatigue and hormonal function in PCOD."

patch_mom_final "$S5" "$FINAL5"
send_mom "$S5"

AI_S8=$(create_item "$CLIENT3_ID" "$S5" "Sunday meal prep — cook for 3 days minimum each Sunday to prevent deadline meal-skipping" "$(date_weeks_ago 7)")
AI_S9=$(create_item "$CLIENT3_ID" "$S5" "Iron-rich foods 3x per week: rajma, palak, ragi roti, or liver" "$(date_weeks_ago 7)")

end_session "$S5"
echo "  ✓ Session 5 done. Meal prep introduced."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 6  (6 weeks ago)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 6 ════════════════════════════════════════"

mark_item "$AI_S8" "completed"  # meal prep working

S6=$(create_session "$CLIENT3_ID" 6 "$(weeks_ago 6)")
echo "  Session ID: $S6"

echo "  Generating brief for S6 (LLM)..."
B6=$(generate_brief "$S6")
print_brief "Sunita — Session 6" "$B6"

NOTES_S6="Meal prep working. Iron foods tracked. Period at day 30 — third straight improvement. Fatigue much better. Weight 66.5kg. Sunita said 'I feel like myself again for the first time in 2 years.' Recommended blood tests to get objective data: testosterone (total + free), fasting insulin, Vitamin D, ferritin. She agreed to book this week."

add_notes "$S6" "$NOTES_S6"

echo "  Generating MOM draft for S6 (LLM)..."
MOM6=$(generate_mom_draft "$S6" "$NOTES_S6")
print_mom_draft "Sunita — Session 6" "$MOM6"
DRAFT6=$(echo "$MOM6" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL6="$DRAFT6

Coach note: 30-day cycle is 40% shorter than baseline (50+ days). Three consecutive improvements over 10 weeks through lifestyle alone. This is the story to anchor her through harder weeks ahead.

The blood test is now essential. We've been working blind — objective hormone data will let us confirm whether insulin resistance is the driver (most likely given PCOD + the improvement from low-sugar diet) and calibrate the next phase accordingly."

patch_mom_final "$S6" "$FINAL6"
send_mom "$S6"

AI_S10=$(create_item "$CLIENT3_ID" "$S6" "Book hormone panel blood test this week: testosterone, fasting insulin, Vitamin D, ferritin" "$(date_weeks_ago 4)")
AI_S11=$(create_item "$CLIENT3_ID" "$S6" "Continue Sunday meal prep — now a permanent weekly habit" "$(date_weeks_ago 4)")

end_session "$S6"
echo "  ✓ Session 6 done. Blood test ordered. Cycle 30 days."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 7  (3 weeks ago)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 7 ════════════════════════════════════════"

mark_item "$AI_S10" "completed"  # blood test done
mark_item "$AI_S11" "completed"  # meal prep maintained

S7=$(create_session "$CLIENT3_ID" 7 "$(weeks_ago 3)")
echo "  Session ID: $S7"

echo "  Generating brief for S7 (LLM)..."
B7=$(generate_brief "$S7")
print_brief "Sunita — Session 7" "$B7"

NOTES_S7="Blood test results: testosterone elevated (borderline), fasting insulin 18 mIU/L (borderline insulin resistance), Vitamin D 18 ng/mL (deficient), ferritin normal. Results reframe the protocol — insulin resistance is confirmed as the primary driver. Low-GI diet is now essential, not optional. Vitamin D supplement started (60,000 IU weekly sachet). Work stress returning — new campaign starting. Screen cutoff still failing — Sunita admitted scrolling until 11pm."

add_notes "$S7" "$NOTES_S7"

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

AI_S12=$(create_item "$CLIENT3_ID" "$S7" "Strict low-GI diet for 4 weeks: no white rice, maida, potato — switch to millets, oats, brown rice" "$(date_weeks_from_now 1)")
AI_S13=$(create_item "$CLIENT3_ID" "$S7" "Daily 20-min walk + 2 yoga sessions per week — insulin sensitivity protocol" "$(date_weeks_from_now 1)")
AI_S14=$(create_item "$CLIENT3_ID" "$S7" "Buy blue light glasses and use every evening — structural fix for screen cutoff failure" "$(date_weeks_from_now 1)")

# Re-log the screen cutoff miss — this is the third time it appears
mark_item "$AI_S6" "missed"  # already missed, but make it visible in history

end_session "$S7"
echo "  ✓ Session 7 done. Insulin resistance confirmed, low-GI protocol started."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 8  (today)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 8 — THE REAL TEST ════════════════════════"

S8=$(create_session "$CLIENT3_ID" 8 "$(today_iso)")
echo "  Session ID: $S8"

echo "  Generating brief for S8 (LLM)..."
B8=$(generate_brief "$S8")
print_brief "Sunita — Session 8" "$B8"

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
echo "  Sunita resume complete. S4-S8 finished."
echo "  Next: bash scripts/mock_p6/05_verify_flywheel.sh"
echo "======================================================="
