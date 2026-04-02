#!/usr/bin/env bash
# Frontend quality checks
# Usage:
#   ./scripts/check-frontend.sh          # check formatting only
#   ./scripts/check-frontend.sh --fix    # auto-fix formatting

set -e

FRONTEND_DIR="$(dirname "$0")/../frontend"
FIX=false

for arg in "$@"; do
    case $arg in
        --fix) FIX=true ;;
    esac
done

echo "==> Frontend quality checks"

# Check that npm/prettier tooling is installed
if ! command -v npm &>/dev/null; then
    echo "ERROR: npm is not installed. Install Node.js to run frontend checks."
    exit 1
fi

cd "$FRONTEND_DIR"

if [ ! -d node_modules ]; then
    echo "  Installing frontend dev dependencies..."
    npm install --silent
fi

if $FIX; then
    echo "  Running Prettier (auto-fix)..."
    npm run format
    echo "  Done. All frontend files formatted."
else
    echo "  Running Prettier (check)..."
    npm run format:check
    echo "  All frontend files are correctly formatted."
fi
