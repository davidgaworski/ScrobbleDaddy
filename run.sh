#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Run Script
#  Usage: bash run.sh
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/ScrobbleDaddy.py"
