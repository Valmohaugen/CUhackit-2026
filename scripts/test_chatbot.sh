#!/usr/bin/env bash
# Quick smoke test for the chatbot API endpoint.
# Usage: bash scripts/test_chatbot.sh [message]
#
# Examples:
#   bash scripts/test_chatbot.sh
#   bash scripts/test_chatbot.sh "Compare ML-DSA-65 vs Falcon-512"

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
MESSAGE="${1:-What is lattice-based cryptography?}"

echo "Sending to $API_URL/api/chatbot:"
echo "  Message: $MESSAGE"
echo "---"

curl -s -X POST "$API_URL/api/chatbot" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"$MESSAGE\"}" | python3 -m json.tool
