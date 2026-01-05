#!/bin/bash
# Refresh fintel data pipeline
# Can be run manually, via cron, or GitHub Actions
#
# Usage:
#   ./scripts/refresh_data.sh           # Run pipeline
#   ./scripts/refresh_data.sh --quiet   # Suppress output (for cron)
#
# Cron example (daily at 6am):
#   0 6 * * * cd /path/to/fintel && ./scripts/refresh_data.sh --quiet >> logs/refresh.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

QUIET=false
if [[ "$1" == "--quiet" ]]; then
    QUIET=true
fi

log() {
    if [[ "$QUIET" == false ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

log "Starting fintel data refresh..."

# Activate virtual environment if exists
if [[ -d ".venv" ]]; then
    source .venv/bin/activate
fi

# Run pipeline
log "Running data pipeline..."
PYTHONPATH=. python scripts/generate_frontend_data.py

# Check if data was generated
if [[ -f "frontend/src/data/report.json" ]]; then
    STOCK_COUNT=$(cat frontend/src/data/report.json | python -c "import sys,json; print(len(json.load(sys.stdin).get('allStocks', [])))")
    log "Success: Generated data for $STOCK_COUNT stocks"
else
    log "ERROR: report.json not found"
    exit 1
fi

# Optional: rebuild frontend (uncomment if needed)
# log "Rebuilding frontend..."
# cd frontend && npm run build

log "Data refresh complete"
