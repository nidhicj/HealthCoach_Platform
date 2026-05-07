#!/usr/bin/env bash
# =============================================================================
# mock_p6/04_sunita.sh
# Sunita Rao — 8 sessions, PCOD management.
#
# Same session-by-session flow as 03_ravi.sh.
# Each brief is generated AFTER updating previous items and BEFORE adding notes.
# By session 8 the brief should reference: insulin resistance from blood tests,
# recurring screen-cutoff failure, low-GI protocol, 7-session cycle trend.
#
# LLM calls: 8 briefs + 8 MOMs = 16 calls
#
# Run from repo root:  cd backend && bash scripts/mock_p6/04_sunita.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids

echo "======================================================="
echo "  Sunita Rao — 8-Session PCOD Management Journey"
echo "  LLM calls: 16 (8 briefs + 8 MOMs)"
echo "======================================================="

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 1  (17 weeks ago)
# Context: zero history
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 1 ════════════════════════════════════════"

S1=$(create_session "$CLIENT3_ID" 1 "$(weeks_ago 17)")
echo "  Session ID: $S1"
print_ast_summary "Sunita before S1" "$CLIENT3_ID"

echo "  Generating brief for S1 (LLM — zero history)..."
B1=$(generate_brief "$S1")
print_brief "Sunita — Session 1 (zero history)" "$B1"

NOTES_S1="Sunita is 28, marketing manager. PCOD diagnosed 2 years ago. Symptoms: irregular cycles (35–50 days), weight gain from 64 to 68kg since diagnosis, fatigue, brain fog. Stressful job — 10-hour days common. Diet: heavy refined carbs, 5 cups sugary tea/day, no vegetables, no exercise. Motivated — wedding in extended family in 6 months is an external trigger but she wants long-term change."

add_notes "$S1" "$NOTES_S1"

echo "  Generating MOM draft for S1 (LLM)..."
MOM1=$(generate_mom_draft "$S1" "$NOTES_S1")
print_mom_draft "Sunita — Session 1" "$MOM1"
DRAFT1=$(echo "$MOM1" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL1="$DRAFT1

Coach note: Start very small. Any restriction that feels like a diet will fail. The only goal this fortnight is sugar elimination and a daily walk. Do not introduce nutrition changes yet — the inflammation baseline needs to shift first.

PCOD context to keep in mind every session: inflammation, cortisol, and insulin are the three levers. Everything we do targets at least one of these."

patch_mom_final "$S1" "$FINAL1"
send_mom "$S1"

AI_S1=$(create_item "$CLIENT3_ID" "$S1" "Eliminate all refined sugar for 2 weeks — no sugar in tea, no biscuits or sweets" "$(date_weeks_ago 15)")
AI_S2=$(create_item "$CLIENT3_ID" "$S1" "15-minute walk every evening after dinner" "$(date_weeks_ago 15)")

end_session "$S1"
echo "  ✓ Session 1 done."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 2  (15 weeks ago)
# Context: sugar elimination (open), walk (open)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 2 ════════════════════════════════════════"

mark_item "$AI_S1" "completed"
mark_item "$AI_S2" "completed"

S2=$(create_session "$CLIENT3_ID" 2 "$(weeks_ago 15)")
echo "  Session ID: $S2"
print_ast_summary "Sunita before S2" "$CLIENT3_ID"

echo "  Generating brief for S2 (LLM)..."
B2=$(generate_brief "$S2")
print_brief "Sunita — Session 2 (S1 both completed)" "$B2"

NOTES_S2="Sugar elimination: 14/14 days — a real achievement. Walk consistent. Energy noticeably better, Sunita reports morning brain fog reduced by about 50%. Period came at day 38 — down from 50+ days. This is an early signal. Introduced anti-inflammatory food basics: turmeric, flaxseeds, walnuts. Tea still at 4 cups (target 2). She says it's a cultural habit, will need gradual reduction."

add_notes "$S2" "$NOTES_S2"

echo "  Generating MOM draft for S2 (LLM)..."
MOM2=$(generate_mom_draft "$S2" "$NOTES_S2")
print_mom_draft "Sunita — Session 2" "$MOM2"
DRAFT2=$(echo "$MOM2" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL2="$DRAFT2

Coach note: The 38-day cycle is a meaningful early signal. Two weeks of sugar elimination produced a measurable hormonal shift. Do not let this slip — it's the foundation everything else rests on.

Tea is a cultural anchor — do not force rapid reduction. 4 to 2 cups over 4 weeks is achievable if she substitutes with herbal tea. Do not make it a restriction conversation; make it a swap conversation."

patch_mom_final "$S2" "$FINAL2"
send_mom "$S2"

AI_S3=$(create_item "$CLIENT3_ID" "$S2" "Add 1 tbsp ground flaxseeds and 5 walnuts to daily diet (anti-inflammatory + omega-3)" "$(date_weeks_ago 13)")
AI_S4=$(create_item "$CLIENT3_ID" "$S2" "Reduce tea gradually to 2 cups per day — swap others with herbal tea or warm water" "$(date_weeks_ago 13)")

end_session "$S2"
echo "  ✓ Session 2 done. Cycle improved to 38 days."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 3  (13 weeks ago)
# Context: flaxseeds/walnuts (open), tea (open)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 3 ════════════════════════════════════════"

mark_item "$AI_S3" "completed"
# Tea still at 3 cups — not yet at 2. Stays open.

S3=$(create_session "$CLIENT3_ID" 3 "$(weeks_ago 13)")
echo "  Session ID: $S3"
print_ast_summary "Sunita before S3" "$CLIENT3_ID"

echo "  Generating brief for S3 (LLM)..."
B3=$(generate_brief "$S3")
print_brief "Sunita — Session 3 (tea reduction still open)" "$B3"

NOTES_S3="Weight same at 68kg (not the focus). Flaxseeds and walnuts added daily. Tea at 3 cups, not 2 yet. Work stress spiked badly — major campaign launch, working until midnight 3 nights this week. Sunita knows stress is a PCOD enemy. Wants tools for cortisol management. Sleep quality poor despite hours."

add_notes "$S3" "$NOTES_S3"

echo "  Generating MOM draft for S3 (LLM)..."
MOM3=$(generate_mom_draft "$S3" "$NOTES_S3")
print_mom_draft "Sunita — Session 3" "$MOM3"
DRAFT3=$(echo "$MOM3" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL3="$DRAFT3

Coach note: The stress spike is the main risk for the next 4 weeks. Cortisol elevation directly disrupts progesterone and worsens PCOD symptoms — this is not abstract. The campaign period is when we need the protocols most.

Box breathing is the highest-ROI intervention for acute cortisol spikes. 5 minutes before bed is achievable even on a midnight-work schedule.

Screen cutoff at 10pm will be the harder one — campaign work bleeds into evenings. Frame it as: blue light suppresses melatonin, which disrupts the cortisol curve, which worsens PCOD. Make the mechanism clear so she understands why it matters."

patch_mom_final "$S3" "$FINAL3"
send_mom "$S3"

AI_S5=$(create_item "$CLIENT3_ID" "$S3" "5-min box breathing before bed every night — cortisol regulation tool" "$(date_weeks_ago 11)")
AI_S6=$(create_item "$CLIENT3_ID" "$S3" "No screens after 10pm — blue light disrupts melatonin and worsens PCOD cortisol cycle" "$(date_weeks_ago 11)")

end_session "$S3"
echo "  ✓ Session 3 done. Cortisol tools introduced."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 4  (11 weeks ago)
# Context: tea (open), breathing (open), screens (open — and will be MISSED)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 4 ════════════════════════════════════════"

# Breathing: done only 4/14 days — still open (not completed, not missed yet — give it another chance)
# Screens after 10pm: campaign work — genuinely missed
mark_item "$AI_S6" "missed"

S4=$(create_session "$CLIENT3_ID" 4 "$(weeks_ago 11)")
echo "  Session ID: $S4"
print_ast_summary "Sunita before S4" "$CLIENT3_ID"

echo "  Generating brief for S4 (LLM)..."
B4=$(generate_brief "$S4")
print_brief "Sunita — Session 4 (screen cutoff missed, breathing open, tea open)" "$B4"

NOTES_S4="Breathing practice inconsistent — 4/14 days. Screen cutoff missed most nights — campaign work ran late. But sleep quality improved slightly even with lower hours. Weight 67.5kg (-0.5kg). Period came at day 33 — another improvement! Second straight shorter cycle. Sunita is encouraged. Introduced morning yoga as a more structured cortisol tool — she responded better to this than the breathing (more tactile)."

add_notes "$S4" "$NOTES_S4"

echo "  Generating MOM draft for S4 (LLM)..."
MOM4=$(generate_mom_draft "$S4" "$NOTES_S4")
print_mom_draft "Sunita — Session 4" "$MOM4"
DRAFT4=$(echo "$MOM4" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")

FINAL4="$DRAFT4

Coach note: Two consecutive cycle improvements (50+ → 38 → 33 days) despite imperfect compliance. This means the dietary foundation (no sugar + anti-inflammatory foods) is carrying the work even when the stress tools slip.

The screen cutoff keeps failing because of an external trigger (work). Address it structurally next session — blue light glasses are the right tool. It removes willpower from the equation entirely."

patch_mom_final "$S4" "$FINAL4"
send_mom "$S4"

AI_S7=$(create_item "$CLIENT3_ID" "$S4" "10-min morning yoga routine daily — replaces evening walk (better cortisol timing in morning)" "$(date_weeks_ago 9)")

end_session "$S4"
echo "  ✓ Session 4 done. Cycle 33 days — second improvement."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 5  (9 weeks ago)
# Context: tea (open), breathing (open), yoga (open), screen cutoff (MISSED from S3)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 5 ════════════════════════════════════════"

mark_item "$AI_S7" "completed"  # yoga stuck

S5=$(create_session "$CLIENT3_ID" 5 "$(weeks_ago 9)")
echo "  Session ID: $S5"
print_ast_summary "Sunita before S5" "$CLIENT3_ID"

echo "  Generating brief for S5 (LLM)..."
B5=$(generate_brief "$S5")
print_brief "Sunita — Session 5 (yoga done, screen still missed in history, tea/breathing open)" "$B5"

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
# Context: tea, breathing, screen (missed), meal prep, iron
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 6 ════════════════════════════════════════"

mark_item "$AI_S8" "completed"  # meal prep working

S6=$(create_session "$CLIENT3_ID" 6 "$(weeks_ago 6)")
echo "  Session ID: $S6"
print_ast_summary "Sunita before S6" "$CLIENT3_ID"

echo "  Generating brief for S6 (LLM)..."
B6=$(generate_brief "$S6")
print_brief "Sunita — Session 6 (meal prep done, screen still missed in history)" "$B6"

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
# Context: tea, breathing, screen (missed x2 now), iron, blood test, meal prep (2nd item)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 7 ════════════════════════════════════════"

mark_item "$AI_S10" "completed"  # blood test done
mark_item "$AI_S11" "completed"  # meal prep maintained

S7=$(create_session "$CLIENT3_ID" 7 "$(weeks_ago 3)")
echo "  Session ID: $S7"
print_ast_summary "Sunita before S7" "$CLIENT3_ID"

echo "  Generating brief for S7 (LLM)..."
B7=$(generate_brief "$S7")
print_brief "Sunita — Session 7 (blood test done, screen still a recurring miss)" "$B7"

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
# SESSION 8  (today — upcoming)
# THIS IS THE REAL TEST.
# Context: 7 sessions of real PCOD narrative, blood test findings, recurring
# screen cutoff failure, insulin resistance protocol, multiple open items.
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
echo "  Sunita done. 8 sessions, 16 LLM calls."
echo "  Compare S1 brief to S8 brief — that progression is the"
echo "  measure of whether the context farm is working."
echo ""
echo "  Next: bash scripts/mock_p6/05_verify_flywheel.sh"
echo "======================================================="
