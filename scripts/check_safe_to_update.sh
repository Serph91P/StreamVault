#!/bin/bash
#
# StreamVault - Safe Update Check Script
# 
# This script checks if it's safe to perform updates by verifying
# that no recordings are currently in progress.
#
# Usage:
#   ./check_safe_to_update.sh [--wait] [--max-wait-minutes 60]
#
# Exit codes:
#   0 - Safe to update (no active recordings)
#   1 - Not safe to update (recordings in progress)
#   2 - Error checking status
#
# Examples:
#   # Simple check
#   ./check_safe_to_update.sh && docker-compose restart
#
#   # Wait up to 30 minutes for recordings to finish
#   ./check_safe_to_update.sh --wait --max-wait-minutes 30
#

set -e

# Configuration
API_URL="${STREAMVAULT_API_URL:-http://localhost:8000}"
ENDPOINT="${API_URL}/api/status/recordings-active"
WAIT_MODE=false
MAX_WAIT_MINUTES=60
CHECK_INTERVAL=60  # Check every 60 seconds

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --wait)
            WAIT_MODE=true
            shift
            ;;
        --max-wait-minutes)
            MAX_WAIT_MINUTES="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--wait] [--max-wait-minutes 60]"
            echo ""
            echo "Options:"
            echo "  --wait                  Wait for recordings to finish (default: false)"
            echo "  --max-wait-minutes N    Maximum minutes to wait (default: 60)"
            echo "  --help                  Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# Function to check status
check_status() {
    local response
    response=$(curl -s -f "$ENDPOINT" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Error: Failed to connect to StreamVault API${NC}" >&2
        echo -e "${YELLOW}  Make sure StreamVault is running at: ${API_URL}${NC}" >&2
        return 2
    fi
    
    echo "$response"
}

# Function to parse JSON (requires jq or python)
get_json_value() {
    local json="$1"
    local key="$2"
    
    # Try jq first
    if command -v jq &> /dev/null; then
        echo "$json" | jq -r ".$key"
    # Fallback to python
    elif command -v python3 &> /dev/null; then
        echo "$json" | python3 -c "import sys, json; print(json.load(sys.stdin)['$key'])"
    else
        echo -e "${RED}Error: Neither jq nor python3 found. Please install one of them.${NC}" >&2
        exit 2
    fi
}

# Main logic
echo -e "${BLUE}🔍 Checking StreamVault recording status...${NC}"
echo -e "${BLUE}   API: ${ENDPOINT}${NC}"
echo ""

if [ "$WAIT_MODE" = true ]; then
    echo -e "${YELLOW}⏳ Wait mode enabled - will wait up to ${MAX_WAIT_MINUTES} minutes for recordings to finish${NC}"
    echo ""
fi

start_time=$(date +%s)
max_wait_seconds=$((MAX_WAIT_MINUTES * 60))

while true; do
    # Check current status
    response=$(check_status)
    status_code=$?
    
    if [ $status_code -eq 2 ]; then
        exit 2
    fi
    
    # Parse response
    safe_to_update=$(get_json_value "$response" "safe_to_update")
    active_count=$(get_json_value "$response" "active_count")
    message=$(get_json_value "$response" "message")
    
    # Get active streamers if any
    if [ "$active_count" != "0" ]; then
        active_streamers=$(get_json_value "$response" "active_streamers" | tr -d '[]"' | tr ',' '\n')
    fi
    
    # Check if safe to update
    if [ "$safe_to_update" = "true" ]; then
        echo -e "${GREEN}✓ Safe to update!${NC}"
        echo -e "${GREEN}  ${message}${NC}"
        exit 0
    fi
    
    # Not safe - check if we should wait
    if [ "$WAIT_MODE" = false ]; then
        echo -e "${RED}✗ Not safe to update${NC}"
        echo -e "${YELLOW}  ${message}${NC}"
        echo ""
        echo -e "${YELLOW}Active recordings:${NC}"
        while IFS= read -r streamer; do
            [ -z "$streamer" ] && continue
            echo -e "  • ${streamer}"
        done <<< "$active_streamers"
        echo ""
        echo -e "${BLUE}Tip: Use --wait to automatically wait for recordings to finish${NC}"
        exit 1
    fi
    
    # Wait mode - check timeout
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    remaining=$((max_wait_seconds - elapsed))
    
    if [ $elapsed -ge $max_wait_seconds ]; then
        echo -e "${RED}✗ Timeout: Recordings still active after ${MAX_WAIT_MINUTES} minutes${NC}"
        echo -e "${YELLOW}  ${message}${NC}"
        echo ""
        echo -e "${YELLOW}Active recordings:${NC}"
        while IFS= read -r streamer; do
            [ -z "$streamer" ] && continue
            echo -e "  • ${streamer}"
        done <<< "$active_streamers"
        exit 1
    fi
    
    # Show waiting status
    remaining_minutes=$((remaining / 60))
    echo -e "${YELLOW}⏳ ${active_count} recording(s) in progress - waiting... (${remaining_minutes}m remaining)${NC}"
    while IFS= read -r streamer; do
        [ -z "$streamer" ] && continue
        echo -e "   • ${streamer}"
    done <<< "$active_streamers"
    
    # Wait before next check
    sleep $CHECK_INTERVAL
    echo "" # New line for next iteration
done
