#!/usr/bin/env bash
# =============================================================================
# mock_p6/01_foundation.sh
# Creates HC user + 3 test clients.
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

# ── Create HC user ─────────────────────────────────────────────────────────────
echo "Creating HC user..."
eval "$(python scripts/create_hc_user.py)"
echo "  HC_ID  = $HC_ID"
echo ""

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

echo "Creating clients..."

CLIENT1_ID=$(create_client '{
  "full_name": "Maya Patel",
  "journey_stage": "onboarding",
  "course_goal": "Build a sustainable morning routine and improve sleep hygiene"
}')
echo "  ✓ Client 1 — Maya Patel (onboarding)  : $CLIENT1_ID"

CLIENT2_ID=$(create_client '{
  "full_name": "Ravi Kumar",
  "journey_stage": "active",
  "course_goal": "Lose 8kg in 16 weeks through consistent nutrition and daily movement"
}')
echo "  ✓ Client 2 — Ravi Kumar  (5 sessions) : $CLIENT2_ID"

CLIENT3_ID=$(create_client '{
  "full_name": "Sunita Rao",
  "journey_stage": "active",
  "course_goal": "Manage PCOD symptoms through anti-inflammatory diet, movement, and stress reduction"
}')
echo "  ✓ Client 3 — Sunita Rao  (8 sessions) : $CLIENT3_ID"

# ── Write env file ─────────────────────────────────────────────────────────────
cat > "$IDS_FILE" <<EOF
HC_JWT=$HC_JWT
HC_ID=$HC_ID
CLIENT1_ID=$CLIENT1_ID
CLIENT2_ID=$CLIENT2_ID
CLIENT3_ID=$CLIENT3_ID
EOF

echo ""
echo "  IDs written to $IDS_FILE"
echo ""
echo "======================================================="
echo "  Stage 1 complete."
echo "  Next: bash scripts/mock_p6/02_seed_history.sh"
echo "======================================================="
