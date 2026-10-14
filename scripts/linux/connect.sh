#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

LAB="$1"
if [ -z "$LAB" ]; then
    echo "======================================================"
    echo " ADLabs WireGuard CLI Connector (Linux)"
    echo "======================================================"
    echo ""
    echo " Available Labs:"
    python3 "$ROOT_DIR/adlabs.py" --list-labs
    TOTAL=$(python3 "$ROOT_DIR/adlabs.py" --count-labs)
    echo ""
    read -rp "Enter lab number (1-$TOTAL) or name: " LAB
fi

if [ -z "$LAB" ]; then
    echo "[x] No lab specified. Exiting..."
    exit 1
fi

python3 "$ROOT_DIR/adlabs.py" --connect "$LAB"
