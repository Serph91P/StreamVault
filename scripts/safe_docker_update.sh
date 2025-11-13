#!/bin/bash
#
# StreamVault - Safe Docker Update Script
#
# This script safely updates StreamVault by waiting for active recordings
# to finish before performing the update.
#
# Usage:
#   ./safe_docker_update.sh [--force] [--max-wait-minutes 60]
#
# Options:
#   --force               Skip recording check and update immediately
#   --max-wait-minutes N  Maximum minutes to wait for recordings (default: 60)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
FORCE_UPDATE=false
MAX_WAIT_MINUTES=60
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_UPDATE=true
            shift
            ;;
        --max-wait-minutes)
            MAX_WAIT_MINUTES="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--force] [--max-wait-minutes 60]"
            echo ""
            echo "Options:"
            echo "  --force               Skip recording check and update immediately (DANGEROUS)"
            echo "  --max-wait-minutes N  Maximum minutes to wait for recordings (default: 60)"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  StreamVault - Safe Docker Update${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Error: Neither docker-compose nor docker found${NC}"
    exit 1
fi

# Determine docker compose command
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}✗ Error: Docker Compose not available${NC}"
    exit 1
fi

echo -e "${BLUE}Using: ${DOCKER_COMPOSE}${NC}"
echo ""

# Step 1: Check for active recordings (unless forced)
if [ "$FORCE_UPDATE" = false ]; then
    echo -e "${YELLOW}Step 1/5: Checking for active recordings...${NC}"
    
    if [ -x "$SCRIPT_DIR/check_safe_to_update.sh" ]; then
        if ! "$SCRIPT_DIR/check_safe_to_update.sh" --wait --max-wait-minutes "$MAX_WAIT_MINUTES"; then
            echo ""
            echo -e "${RED}✗ Update aborted: Active recordings detected${NC}"
            echo -e "${YELLOW}  Use --force to update anyway (may interrupt recordings)${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}⚠ Warning: check_safe_to_update.sh not found or not executable${NC}"
        echo -e "${YELLOW}  Skipping recording check...${NC}"
    fi
else
    echo -e "${RED}⚠ WARNING: Force mode enabled - skipping recording check!${NC}"
    echo -e "${YELLOW}  This may interrupt active recordings!${NC}"
    echo ""
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${BLUE}Update cancelled${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${GREEN}✓ Safe to proceed with update${NC}"
echo ""

# Step 2: Pull latest images
echo -e "${YELLOW}Step 2/5: Pulling latest Docker images...${NC}"
$DOCKER_COMPOSE pull
echo -e "${GREEN}✓ Images pulled${NC}"
echo ""

# Step 3: Stop containers
echo -e "${YELLOW}Step 3/5: Stopping containers...${NC}"
$DOCKER_COMPOSE down
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

# Step 4: Start containers with new images
echo -e "${YELLOW}Step 4/5: Starting updated containers...${NC}"
$DOCKER_COMPOSE up -d
echo -e "${GREEN}✓ Containers started${NC}"
echo ""

# Step 5: Verify services are running
echo -e "${YELLOW}Step 5/5: Verifying services...${NC}"
sleep 5  # Give services time to start

if $DOCKER_COMPOSE ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Services are running${NC}"
else
    echo -e "${RED}✗ Warning: Some services may not be running${NC}"
    echo -e "${YELLOW}  Run '$DOCKER_COMPOSE ps' to check status${NC}"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Update completed successfully!${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  • Check logs: ${YELLOW}$DOCKER_COMPOSE logs -f${NC}"
echo -e "  • Check status: ${YELLOW}$DOCKER_COMPOSE ps${NC}"
echo -e "  • Open UI: ${YELLOW}http://localhost:8000${NC}"
echo ""
