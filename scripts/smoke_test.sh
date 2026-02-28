#!/bin/bash
# Smoke test: verify all API endpoints are responding
set -e

BASE=${API_URL:-http://localhost:8000}
PASS=0
FAIL=0

check() {
    local desc="$1"
    local method="$2"
    local url="$3"
    local data="$4"

    if [ "$method" = "GET" ]; then
        status=$(curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    else
        status=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$url" \
            -H "Content-Type: application/json" -d "$data" 2>/dev/null || echo "000")
    fi

    if [ "$status" = "200" ]; then
        echo "  PASS  $desc ($status)"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $desc ($status)"
        FAIL=$((FAIL + 1))
    fi
}

echo "Quantum DNS Shield - Smoke Test"
echo "================================"
echo "Target: $BASE"
echo ""

check "Health check"        GET  "$BASE/api/health"
check "Get config"          GET  "$BASE/api/config"
check "Set config"          POST "$BASE/api/config" '{"source":"qrng","scheme":"ml-dsa-65"}'
check "Resolve domain"      POST "$BASE/api/resolve" '{"domain":"example.com"}'
check "Live metrics"        GET  "$BASE/api/metrics/live"
check "QRNG status"         GET  "$BASE/api/qrng/status"
check "Benchmarks"          GET  "$BASE/api/benchmarks"
check "Migration matrix"    GET  "$BASE/api/migration"
check "Start Shor's"        POST "$BASE/api/attack/shors" '{"n":15}'
check "Shor's status"       GET  "$BASE/api/attack/shors"

echo ""
echo "Results: $PASS passed, $FAIL failed"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
echo "All smoke tests passed!"
