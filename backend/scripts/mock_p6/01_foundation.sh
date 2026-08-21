#!/usr/bin/env bash
# =============================================================================
# mock_p6/01_foundation.sh
# Creates HC user + 1 test client (Maya only — trimmed down from the original
# 3-client version to avoid the slow, LLM-heavy 02/03/04 scripts; this stage
# itself has no LLM calls, so it stays fast regardless).
# Writes all IDs and the JWT to /tmp/mock_p6_ids.env for subsequent scripts.
#
# Run from repo root:
#   cd backend && bash scripts/mock_p6/01_foundation.sh
# =============================================================================
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
IDS_FILE="/tmp/mock_p6_ids.env"
API="http://localhost:8000"

echo "======================================================="
echo "  P6 Mock Test — Stage 1: Foundation"
echo "======================================================="
echo ""

# ── Activate venv ─────────────────────────────────────────────────────────────
source /mnt/hdd/yourProjects/venv/hc_pf/bin/activate
cd "$BACKEND_DIR"

# ── HC email — must match the Google account you will log in with ─────────────
# Change this if you want to use a different Gmail account.
HC_EMAIL="joshichi.nidhi@gmail.com"

# ── Create HC user ─────────────────────────────────────────────────────────────
echo "Creating HC user ($HC_EMAIL)..."
eval "$(python scripts/create_hc_user.py --email "$HC_EMAIL")"
echo "  HC_ID  = $HC_ID"
echo "  Email  = $HC_EMAIL"
echo ""

source "$BACKEND_DIR/scripts/mock_p6/lib.sh"
verify_hint "HC user created" \
  "DB:       psql \$DB -c \"SELECT id, email, google_sub FROM users WHERE id = '$HC_ID';\"" \
  "API:      curl -s http://localhost:8000/api/users/me -H 'Authorization: Bearer \$HC_JWT' | python3 -m json.tool" \
  "Design:   google_sub will be 'pending-oauth-...' until you log in via Google OAuth in the frontend." \
  "Design:   On first Google login, the auth router finds this row by email and updates google_sub in place." \
  "Design:   After that login, the frontend will show all mock data under your real Google account."

# ── Helper: create client ──────────────────────────────────────────────────────
create_client() {
  local payload="$1"
  curl -s -X POST "$API/api/clients" \
    -H "Authorization: Bearer $HC_JWT" \
    -H "Content-Type: application/json" \
    -d "$payload" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
if 'id' not in data:
    print('ERROR: ' + json.dumps(data), file=sys.stderr)
    sys.exit(1)
print(data['id'])
"
}

echo "Creating client..."

CLIENT1_ID=$(create_client '{
  "full_name": "Maya Patel",
  "email": "maya.patel@mock.tapas.test",
  "journey_stage": "onboarding",
  "course_goal": "Build a sustainable morning routine and improve sleep hygiene"
}')
echo "  ✓ Client 1 — Maya Patel (onboarding)  : $CLIENT1_ID"

verify_hint "1 client created" \
  "DB:       psql \$DB -c \"SELECT full_name, journey_stage, code FROM clients WHERE hc_user_id = '$HC_ID' ORDER BY created_at;\"" \
  "API:      curl -s http://localhost:8000/api/clients -H 'Authorization: Bearer \$HC_JWT' | python3 -m json.tool" \
  "Frontend: http://localhost:3000/clients  →  Maya should appear as 1 card" \
  "Design:   journey_stage = onboarding for Maya. code (CP-XXXX) auto-assigned."

# ── Write env file ─────────────────────────────────────────────────────────────
cat > "$IDS_FILE" <<EOF
HC_JWT=$HC_JWT
HC_ID=$HC_ID
CLIENT1_ID=$CLIENT1_ID
EOF

echo ""
echo "  IDs written to $IDS_FILE"
echo ""
echo "======================================================="
echo "  Stage 1 complete (trimmed to 1 client — Ravi/Sunita and the"
echo "  LLM-heavy 02/03/04 scripts were skipped for speed)."
echo "======================================================="

