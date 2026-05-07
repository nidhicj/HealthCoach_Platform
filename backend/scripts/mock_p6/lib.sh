#!/usr/bin/env bash
# =============================================================================
# mock_p6/lib.sh  — shared functions sourced by all mock_p6 scripts
# =============================================================================

API="http://localhost:8000"
DB="postgresql://postgres:localdevpassword@localhost:5432/parivarthan_dev"
IDS_FILE="/tmp/mock_p6_ids.env"

# ── HTTP helpers ───────────────────────────────────────────────────────────────

_post() {
  local path="$1"; local data="$2"
  curl -s -X POST "$API$path" \
    -H "Authorization: Bearer $HC_JWT" \
    -H "Content-Type: application/json" \
    -d "$data"
}

_patch() {
  local path="$1"; local data="$2"
  curl -s -X PATCH "$API$path" \
    -H "Authorization: Bearer $HC_JWT" \
    -H "Content-Type: application/json" \
    -d "$data"
}

_get() {
  local path="$1"
  curl -s "$API$path" -H "Authorization: Bearer $HC_JWT"
}

# ── JSON helpers ───────────────────────────────────────────────────────────────

get_id() {
  python3 -c "
import sys, json
d = json.load(sys.stdin)
if 'id' not in d:
    import sys; print('ERROR: ' + json.dumps(d), file=sys.stderr); sys.exit(1)
print(d['id'])
"
}

json_str() {
  # Safely JSON-encode a bash string for embedding in a payload
  python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$1"
}

# ── Date helpers ───────────────────────────────────────────────────────────────

weeks_ago() {
  python3 -c "
from datetime import datetime, timedelta, timezone
print((datetime.now(timezone.utc) - timedelta(weeks=$1)).strftime('%Y-%m-%dT10:00:00Z'))
"
}

today_iso() {
  python3 -c "from datetime import datetime,timezone; print(datetime.now(timezone.utc).strftime('%Y-%m-%dT10:00:00Z'))"
}

date_weeks_from_now() {
  python3 -c "
from datetime import date, timedelta
print((date.today() + timedelta(weeks=$1)).isoformat())
"
}

date_weeks_ago() {
  python3 -c "
from datetime import date, timedelta
print((date.today() - timedelta(weeks=$1)).isoformat())
"
}

# ── Session lifecycle ──────────────────────────────────────────────────────────

create_session() {
  local client_id="$1"; local num="$2"; local scheduled_at="$3"
  _post "/api/sessions" "{
    \"client_id\": \"$client_id\",
    \"session_number\": $num,
    \"scheduled_at\": \"$scheduled_at\"
  }" | get_id
}

add_notes() {
  local session_id="$1"; local notes="$2"
  _patch "/api/sessions/$session_id" "{\"session_notes\": $(json_str "$notes")}" > /dev/null
}

# Calls the LLM and returns the full brief JSON
generate_brief() {
  local session_id="$1"
  _get "/api/sessions/$session_id/brief"
}

# Calls the LLM and returns the full mom JSON
generate_mom_draft() {
  local session_id="$1"; local notes="$2"
  _post "/api/sessions/$session_id/mom/draft" "{\"session_notes\": $(json_str "$notes")}"
}

patch_mom_final() {
  local session_id="$1"; local final_text="$2"
  _patch "/api/sessions/$session_id/mom" "{\"final_text\": $(json_str "$final_text")}" > /dev/null
}

send_mom() {
  local session_id="$1"
  _post "/api/sessions/$session_id/mom/send" '{}' > /dev/null
}

end_session() {
  local session_id="$1"
  _post "/api/sessions/$session_id/end" '{}' > /dev/null
}

# ── Action item helpers ────────────────────────────────────────────────────────

create_item() {
  local client_id="$1"; local session_id="$2"; local description="$3"; local due_date="$4"
  _post "/api/action-items" "{
    \"client_id\": \"$client_id\",
    \"session_id\": \"$session_id\",
    \"description\": $(json_str "$description"),
    \"due_date\": \"$due_date\"
  }" | get_id
}

mark_item() {
  local item_id="$1"; local status="$2"
  _patch "/api/action-items/$item_id" "{\"status\": \"$status\"}" > /dev/null
}

# ── Display helpers ────────────────────────────────────────────────────────────

print_brief() {
  local session_label="$1"; local brief_json="$2"
  echo ""
  echo "  ┌─ BRIEF: $session_label ─────────────────────────────────"
  echo "$brief_json" | python3 -c "
import sys, json
b = json.load(sys.stdin)
text = b.get('brief_text', 'ERROR: no brief_text in response')
flags = b.get('triage_flags', [])
for line in text.splitlines():
    print('  │  ' + line)
if flags:
    print('  │')
    print('  │  triage_flags: ' + str(flags))
print('  └────────────────────────────────────────────────────────')
"
  echo ""
}

print_mom_draft() {
  local session_label="$1"; local mom_json="$2"
  echo ""
  echo "  ┌─ MOM DRAFT: $session_label ──────────────────────────────"
  echo "$mom_json" | python3 -c "
import sys, json
m = json.load(sys.stdin)
text = m.get('draft_text', 'ERROR: no draft_text in response')
for line in text.splitlines():
    print('  │  ' + line)
print('  └────────────────────────────────────────────────────────')
"
  echo ""
}

print_ast_summary() {
  local client_label="$1"; local client_id="$2"
  local ast
  ast=$(_get "/api/clients/$client_id/ast")
  echo "$ast" | python3 -c "
import sys, json
ast = json.load(sys.stdin)
open_  = ast.get('open_items', [])
missed = ast.get('missed_items', [])
flags  = ast.get('triage_flags', [])
print(f'  AST before brief: {len(open_)} open, {len(missed)} missed, flags={flags}')
for i in open_:  print(f'    open   → {i[\"description\"][:70]}')
for i in missed: print(f'    missed ✗ {i[\"description\"][:70]}')
"
}

# ── Verification hint printer ─────────────────────────────────────────────────
#
# Usage:
#   verify_hint "Label" \
#     "DB:       <psql query>" \
#     "API:      <curl command>" \
#     "Frontend: <URL or description>" \
#     "Design:   <why this matters>"
#
# Print as many or as few lines as are relevant.

verify_hint() {
  local header="$1"; shift
  echo ""
  echo "  ┌─ VERIFY ── $header"
  for line in "$@"; do
    echo "  │  $line"
  done
  echo "  └─────────────────────────────────────────────────────────────"
  echo ""
}

# Shorthand for a DB-only psql one-liner hint
db_hint() {
  local label="$1"; local sql="$2"
  verify_hint "$label" \
    "DB: psql \$DB -c \"$sql\""
}

# ── Guard ──────────────────────────────────────────────────────────────────────

require_ids() {
  if [ ! -f "$IDS_FILE" ]; then
    echo "ERROR: $IDS_FILE not found. Run 01_foundation.sh first."
    exit 1
  fi
  source "$IDS_FILE"
}
