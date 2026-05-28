#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Run Script
#  Usage: bash run.sh
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find conda
for path in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -d "$path" ]; then
        CONDA_DIR="$path"
        break
    fi
done

cd "$SCRIPT_DIR"
"$CONDA_DIR/envs/ScrobbleDaddyPy/bin/python" ScrobbleDaddy.py
