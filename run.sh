#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Run Script
#  Usage: bash run.sh
# =============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Find and activate conda
for path in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -f "$path/etc/profile.d/conda.sh" ]; then
        source "$path/etc/profile.d/conda.sh"
        break
    fi
done

conda activate ScrobbleDaddyPy
cd "$SCRIPT_DIR"
python ScrobbleDaddy.py
