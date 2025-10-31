#!/bin/bash

# Test script for Perps Funding Pulse API endpoints
# Usage: ./test_endpoints.sh [BASE_URL]

BASE_URL=${1:-"http://localhost:8000"}

echo "Testing Perps Funding Pulse API at: $BASE_URL"
echo "================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Helper function to test endpoint
test_endpoint() {
    local name=$1
    local method=$2
    local endpoint=$3
    local expected_status=$4
    local data=$5

    echo -n "Testing $name... "

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" "$BASE_URL$endpoint")
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$BASE_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    fi

    status_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)

    if [ "$status_code" = "$expected_status" ]; then
        echo -e "${GREEN}PASSED${NC} (HTTP $status_code)"
        ((PASSED++))
        if [ -n "$body" ]; then
            echo "$body" | jq '.' 2>/dev/null || echo "$body"
        fi
    else
        echo -e "${RED}FAILED${NC} (Expected HTTP $expected_status, got $status_code)"
        ((FAILED++))
        echo "$body"
    fi
    echo ""
}

# Test 1: Health Check
test_endpoint "Health Check" "GET" "/health" "200"

# Test 2: List Venues
test_endpoint "List Venues" "GET" "/venues" "200"

# Test 3: Landing Page
test_endpoint "Landing Page" "GET" "/" "200"

# Test 4: AP2 Metadata (agent.json)
test_endpoint "AP2 Metadata" "GET" "/.well-known/agent.json" "200"

# Test 5: x402 Metadata
test_endpoint "x402 Metadata" "GET" "/.well-known/x402" "402"

# Test 6: Funding Data - Binance BTC
test_endpoint "Funding Data (Binance BTC)" "POST" "/perps/funding" "200" \
    '{"venue_ids":["binance"],"markets":["BTC/USDT:USDT"]}'

# Test 7: Funding Data - Multiple Venues
test_endpoint "Funding Data (Multi-Venue)" "POST" "/perps/funding" "200" \
    '{"venue_ids":["binance","bybit"],"markets":["BTC/USDT:USDT","ETH/USDT:USDT"]}'

# Test 8: Funding Data - Invalid Venue
test_endpoint "Invalid Venue (Should Fail)" "POST" "/perps/funding" "400" \
    '{"venue_ids":["invalid"],"markets":["BTC/USDT:USDT"]}'

# Test 9: Funding Data - Missing Fields
test_endpoint "Missing Fields (Should Fail)" "POST" "/perps/funding" "422" \
    '{"venue_ids":["binance"]}'

# Test 10: AP2 Entrypoint
test_endpoint "AP2 Entrypoint" "POST" "/entrypoints/perps-funding-pulse/invoke" "200" \
    '{"venue_ids":["binance"],"markets":["BTC/USDT:USDT"]}'

# Summary
echo "================================================"
echo "Test Summary:"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "================================================"

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
