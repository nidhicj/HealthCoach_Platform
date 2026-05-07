#!/usr/bin/env bash
# =============================================================================
# mock_p6/03_ravi.sh
# Ravi Kumar — 5 sessions, weight loss journey.
#
# Each session follows the exact real-life sequence:
#   1. Mark previous session's items completed/missed (coach knows from client)
#   2. Create session
#   3. Print AST snapshot — this is what the brief will draw from
#   4. Generate brief (LLM) — context = items from sessions 1..N-1 only
#   5. Add session notes
#   6. Generate MOM draft (LLM)
#   7. HC edits draft (style snippet captured from sessions 2+)
#   8. Send MOM
#   9. Create this session's action items
#   10. End session
#
# LLM calls: 5 briefs + 5 MOMs = 10 calls
#
# Run from repo root:  cd backend && bash scripts/mock_p6/03_ravi.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/lib.sh"
require_ids
DB="postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev"

echo "======================================================="
echo "  Ravi Kumar — 5-Session Weight Loss Journey"
echo "  LLM calls: 10 (5 briefs + 5 MOMs)"
echo "======================================================="

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 1  (9 weeks ago)
# Context going in: nothing — first session
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 1 ════════════════════════════════════════"

S1=$(create_session "$CLIENT2_ID" 1 "$(weeks_ago 9)")
echo "  Session ID: $S1"
print_ast_summary "Ravi before S1" "$CLIENT2_ID"

echo "  Generating brief for S1 (LLM)..."
B1=$(generate_brief "$S1")
print_brief "Ravi — Session 1 (zero history)" "$B1"

verify_hint "S1 brief — zero-history baseline (save the input_tokens number)" \
  "DB:       psql \$DB -c \"SELECT lc.input_tokens, lc.output_tokens FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id WHERE b.session_id = '$S1';\"" \
  "Design:   Note this input_tokens value. Each subsequent session should be LARGER." \
  "Design:   The AST above showed 0 open, 0 missed. Brief must not invent any history."

NOTES_S1="First session. Ravi is 34, IT lead, fully sedentary. Weight: 88kg, target 80kg in 16 weeks. Eating out 5 days/week — canteen meals averaging 950 kcal each. No exercise at all. Sleep is good at 7.5 hours — an asset. Motivation high: daughter born 6 months ago, wants energy to keep up with her. Discussed starting small — a daily walk and calorie awareness."

add_notes "$S1" "$NOTES_S1"

echo "  Generating MOM draft for S1 (LLM)..."
MOM1=$(generate_mom_draft "$S1" "$NOTES_S1")
print_mom_draft "Ravi — Session 1" "$MOM1"

DRAFT1=$(echo "$MOM1" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")
FINAL1="$DRAFT1

Coach note: The daughter motivation is strong — use it. Avoid overwhelming with too many changes. Walk and calorie awareness are the only two levers for the next 2 weeks. Do not introduce diet changes yet."

patch_mom_final "$S1" "$FINAL1"
send_mom "$S1"

AI_R1=$(create_item "$CLIENT2_ID" "$S1" "20-min morning walk every day before work" "$(date_weeks_ago 7)")
AI_R2=$(create_item "$CLIENT2_ID" "$S1" "Log all meals in MyFitnessPal for 2 weeks — awareness only, no restriction yet" "$(date_weeks_ago 7)")

end_session "$S1"
echo "  ✓ Session 1 done. 2 items created."

verify_hint "S1 action items created — context seeded for S2 brief" \
  "DB:       psql \$DB -c \"SELECT description, status FROM action_items WHERE session_id = '$S1';\"" \
  "Design:   2 open items now in DB. S2 brief will see both via AST. S1 brief saw neither (generated before these)."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 2  (7 weeks ago)
# Context: 2 open items from S1 (walk + logging)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 2 ════════════════════════════════════════"

# Coach receives client update before session: walk done, logging done
mark_item "$AI_R1" "completed"
mark_item "$AI_R2" "completed"

verify_hint "S1 items marked completed — AST now shows zero open" \
  "DB:       psql \$DB -c \"SELECT description, status FROM action_items WHERE client_id = '$CLIENT2_ID' ORDER BY created_at;\"" \
  "Design:   Both items now 'completed'. AST will show 0 open, 0 missed — brief will acknowledge wins, not flag risks."

S2=$(create_session "$CLIENT2_ID" 2 "$(weeks_ago 7)")
echo "  Session ID: $S2"
print_ast_summary "Ravi before S2" "$CLIENT2_ID"

echo "  Generating brief for S2 (LLM)..."
B2=$(generate_brief "$S2")
print_brief "Ravi — Session 2 (S1 items both completed)" "$B2"

verify_hint "S2 brief — input_tokens should be LARGER than S1" \
  "DB:       psql \$DB -c \"SELECT b.session_id, lc.input_tokens FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id WHERE b.session_id IN ('$S1','$S2') ORDER BY lc.created_at;\"" \
  "Design:   S2 input_tokens > S1 input_tokens confirms the context farm is injecting prior session data." \
  "Design:   S2 brief should mention that S1 items were both completed — not just repeat the goal."

NOTES_S2="Walk habit solid: 14/14 days. Calorie logging revealed average 2100 kcal/day — canteen lunch is 950 kcal alone. Weight 87.2kg (-0.8kg). Protein severely low at 45g/day — the main nutritional gap. Discussed protein sources: eggs, dahi, dal. Client open to it. Walk extended to 30 min naturally — client is enjoying it."

add_notes "$S2" "$NOTES_S2"

echo "  Generating MOM draft for S2 (LLM)..."
MOM2=$(generate_mom_draft "$S2" "$NOTES_S2")
print_mom_draft "Ravi — Session 2" "$MOM2"

DRAFT2=$(echo "$MOM2" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")
FINAL2="$DRAFT2

Coach note: Protein is now the single most important variable. Fat loss will stall without it. Keep walk as a habit — it no longer needs monitoring. Redirect client attention fully to protein over the next 2 weeks.

Priority hierarchy for M003: protein first, everything else second."

patch_mom_final "$S2" "$FINAL2"
send_mom "$S2"

verify_hint "S2 MOM — style snippet #2 should appear" \
  "DB:       psql \$DB -c \"SELECT COUNT(*) AS snippet_count FROM hc_style_snippets WHERE hc_user_id = '$HC_ID';\"" \
  "DB:       psql \$DB -c \"SELECT snippet_type, left(hc_modified_text,80) FROM hc_style_snippets WHERE hc_user_id = '$HC_ID' ORDER BY created_at;\"" \
  "Design:   After Maya M001 (1 snippet) + Ravi S2 (1 snippet) = 2 total. Each HC edit adds one." \
  "Design:   If count is still 1, check that moms.llm_call_id is set and final_text differs from draft_text."

AI_R3=$(create_item "$CLIENT2_ID" "$S2" "Increase daily protein to 80g: eggs at breakfast, dahi at lunch, dal at dinner" "$(date_weeks_ago 5)")
AI_R4=$(create_item "$CLIENT2_ID" "$S2" "Extend morning walk to 30 min (already happening naturally — formalise it)" "$(date_weeks_ago 5)")

end_session "$S2"
echo "  ✓ Session 2 done. 2 new items, S1 items both completed."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 3  (5 weeks ago)
# Context: protein target (open), walk extension (open)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 3 ════════════════════════════════════════"

# Walk extension naturally achieved — mark completed
mark_item "$AI_R4" "completed"
# Protein not yet at 80g — stays open

S3=$(create_session "$CLIENT2_ID" 3 "$(weeks_ago 5)")
echo "  Session ID: $S3"
print_ast_summary "Ravi before S3" "$CLIENT2_ID"

echo "  Generating brief for S3 (LLM)..."
B3=$(generate_brief "$S3")
print_brief "Ravi — Session 3 (protein open, walk done)" "$B3"

NOTES_S3="Weight 86.5kg (-0.7kg, -1.5kg total). 30-min walk consistent. Protein improving — hitting 65g/day, still short of 80g (missing dal at dinner mostly). Sleep fell to 6 hours this week — major project deadline. Energy noticeably lower. Client aware that sleep is affecting him. Discussed cortisol and fat loss relationship. He understands and wants to protect sleep but says deadlines are unpredictable."

add_notes "$S3" "$NOTES_S3"

echo "  Generating MOM draft for S3 (LLM)..."
MOM3=$(generate_mom_draft "$S3" "$NOTES_S3")
print_mom_draft "Ravi — Session 3" "$MOM3"

DRAFT3=$(echo "$MOM3" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")
FINAL3="$DRAFT3

Coach note: Sleep is now the primary risk. Cortisol from under-sleep directly counteracts fat loss — this is not a soft concern. The weight trend is good but fragile. If sleep stays at 6h for 3 weeks, progress will stall.

Introduce strength training now while momentum is high — it accelerates the metabolic shift and gives him a reason to protect sleep (you recover from training during sleep)."

patch_mom_final "$S3" "$FINAL3"
send_mom "$S3"

AI_R5=$(create_item "$CLIENT2_ID" "$S3" "Protect minimum 7.5 hours sleep — non-negotiable even during work deadlines" "$(date_weeks_ago 3)")
AI_R6=$(create_item "$CLIENT2_ID" "$S3" "Start 2 bodyweight strength sessions per week — home, no gym needed, 20 min each" "$(date_weeks_ago 3)")

end_session "$S3"
echo "  ✓ Session 3 done. Sleep risk flagged, strength introduced."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 4  (3 weeks ago)
# Context: protein (open), sleep (open), strength x2 (open)
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 4 ════════════════════════════════════════"

# Sleep recovered — completed. Strength missed.
mark_item "$AI_R5" "completed"
mark_item "$AI_R6" "missed"

verify_hint "S3 strength item marked MISSED — AST should flag it" \
  "DB:       psql \$DB -c \"SELECT description, status FROM action_items WHERE client_id = '$CLIENT2_ID' AND status = 'missed';\"" \
  "API:      curl -s http://localhost:8000/api/clients/$CLIENT2_ID/ast -H 'Authorization: Bearer \$HC_JWT' | python3 -m json.tool" \
  "Frontend: http://localhost:3000/clients/$CLIENT2_ID  →  missed items appear with a warning indicator" \
  "Design:   The AST should now show this in missed_items. The S4 brief will receive it as a triage flag." \
  "Design:   This is testing whether missed items surface as risks in the next session prep."

S4=$(create_session "$CLIENT2_ID" 4 "$(weeks_ago 3)")
echo "  Session ID: $S4"
print_ast_summary "Ravi before S4" "$CLIENT2_ID"

echo "  Generating brief for S4 (LLM)..."
B4=$(generate_brief "$S4")
print_brief "Ravi — Session 4 (strength missed, protein still open)" "$B4"

verify_hint "S4 brief — first time a missed item should appear" \
  "DB:       psql \$DB -c \"SELECT lc.input_tokens FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id WHERE b.session_id = '$S4';\"" \
  "Design:   input_tokens should be noticeably larger than S1/S2. The missed item adds context tokens." \
  "Design:   Brief should explicitly name the missed strength session from S3 as a risk/carry-over."

NOTES_S4="Weight 85.8kg (-0.7kg, -2.2kg total). Sleep back to 7 hours. Strength sessions missed — fatigue after deadline, felt unable to start. Protein now at 72g/day — closer. Weekend cravings spiked hard on Saturday: social dinner, Sunday brunch. Client estimates extra 1000 kcal across the weekend. Identified weekends as the main vulnerability. Wife and family social eating is the trigger. Client wants a weekend strategy."

add_notes "$S4" "$NOTES_S4"

echo "  Generating MOM draft for S4 (LLM)..."
MOM4=$(generate_mom_draft "$S4" "$NOTES_S4")
print_mom_draft "Ravi — Session 4" "$MOM4"

DRAFT4=$(echo "$MOM4" | python3 -c "import sys,json; print(json.load(sys.stdin)['draft_text'])")
FINAL4="$DRAFT4

Coach note: 2.2kg in 6 weeks is on track. The strength miss is understandable but it becomes a pattern if it happens twice. Weekend eating is now the clearest blocker — it's a structural problem (unplanned social eating), not a willpower problem. The fix is structural: plan meals on Friday, shop for them, social exceptions are budgeted in.

Strength sessions need to be scheduled like meetings — not optional, not 'when I feel like it.'"

patch_mom_final "$S4" "$FINAL4"
send_mom "$S4"

AI_R7=$(create_item "$CLIENT2_ID" "$S4" "Plan all weekend meals on Friday evening — write the plan, shop for it" "$(date_weeks_ago 1)")
AI_R8=$(create_item "$CLIENT2_ID" "$S4" "Schedule 2 strength sessions as recurring calendar blocks — treat like meetings" "$(date_weeks_ago 1)")

end_session "$S4"
echo "  ✓ Session 4 done. Strength missed, weekend plan introduced."

# ─────────────────────────────────────────────────────────────────────────────
# SESSION 5  (today — upcoming)
# Context: protein (open), weekend plan (open), calendar strength (open), missed strength from S3
# This is the REAL TEST: does the brief surface all of this coherently?
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "══ SESSION 5 — THE REAL TEST ════════════════════════"
echo "  4 sessions of real history now in DB."
echo "  Brief should surface: protein progress, missed S3 strength, S4 open items."
echo ""

S5=$(create_session "$CLIENT2_ID" 5 "$(today_iso)")
echo "  Session ID: $S5"
print_ast_summary "Ravi before S5" "$CLIENT2_ID"

echo "  Generating brief for S5 (LLM)..."
B5=$(generate_brief "$S5")
print_brief "Ravi — Session 5 (4 sessions of real context)" "$B5"

verify_hint "S5 brief — THE KEY TOKEN PROGRESSION CHECK" \
  "DB:       psql \$DB -c \"SELECT s.session_number, lc.input_tokens FROM llm_calls lc JOIN briefs b ON b.llm_call_id = lc.id JOIN sessions s ON s.id = b.session_id WHERE s.client_id = '$CLIENT2_ID' ORDER BY s.session_number;\"" \
  "Design:   input_tokens MUST grow from S1 → S5. A flat or shrinking curve means context is not accumulating." \
  "Design:   S5 should also have snippet_count > 0 in llm_calls — style context injected from prior MOM edits." \
  "DB:       psql \$DB -c \"SELECT lc.snippet_count, lc.snippet_tokens FROM llm_calls lc JOIN moms m ON m.llm_call_id = lc.id JOIN sessions s ON s.id = m.session_id WHERE s.id = '$S5' AND lc.use_case = 'mom_generation';\"" \
  "Frontend: http://localhost:3000/clients/$CLIENT2_ID  →  5 sessions listed, latest is today's"

echo "  ─── EVALUATE SESSION 5 BRIEF ──────────────────────"
echo "  □  Mentions protein target still open (ongoing from S2)?"
echo "  □  Flags the missed strength session from S3?"
echo "  □  References the weekend eating as a known pattern?"
echo "  □  Shows weight trend or progress?"
echo "  □  Does NOT confuse items across sessions?"
echo "  ────────────────────────────────────────────────────"
echo ""

NOTES_S5="Ravi hit 2 strength sessions this week — first time meeting the target. Weight 85.2kg (-0.6kg, -2.8kg total). Protein at 76g/day. Weekend plan partially worked: Friday planning done, Saturday stayed on track, Sunday family lunch went over but he recovered by keeping Monday light. He's noticeably more energetic. Wife also started eating healthier — family buy-in now strong. He asked about adding a third strength session. Advised to consolidate 2x first."

add_notes "$S5" "$NOTES_S5"

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

# Save session IDs
cat >> "$IDS_FILE" <<EOF
S_RAVI_1=$S1
S_RAVI_2=$S2
S_RAVI_3=$S3
S_RAVI_4=$S4
S_RAVI_5=$S5
EOF

echo ""
echo "======================================================="
echo "  Ravi done. 5 sessions, 10 LLM calls."
echo "  Briefs should show progression: S1 sparse → S5 rich."
echo "  Next: bash scripts/mock_p6/04_sunita.sh"
echo "======================================================="
