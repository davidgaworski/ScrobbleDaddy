#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Auto-Start Setup Script
#  Run this once to make ScrobbleDaddy launch on every boot.
#
#  Usage:
#    bash setup_autostart.sh           # Enable auto-start
#    bash setup_autostart.sh --remove  # Disable auto-start
# =============================================================

DESKTOP_FILE="$HOME/.config/autostart/scrobbledaddy.desktop"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ----------------------------------------------------------
#  Remove mode
# ----------------------------------------------------------
if [ "$1" = "--remove" ]; then
    if [ -f "$DESKTOP_FILE" ]; then
        rm "$DESKTOP_FILE"
        echo ""
        echo "✅  Auto-start has been disabled."
        echo "    ScrobbleDaddy will no longer launch on boot."
    else
        echo ""
        echo "ℹ️   Auto-start was not enabled — nothing to remove."
    fi
    exit 0
fi

# ----------------------------------------------------------
#  Find Conda
# ----------------------------------------------------------
CONDA_SH=""
for path in "$HOME/miniconda3" "$HOME/miniforge3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -f "$path/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$path/etc/profile.d/conda.sh"
        break
    fi
done

if [ -z "$CONDA_SH" ]; then
    echo ""
    echo "❌  Could not find a Conda installation."
    echo "    Looked in: ~/miniconda3, ~/miniforge3, ~/anaconda3, ~/mambaforge"
    echo ""
    echo "    If Conda is installed somewhere else, edit this script and"
    echo "    set CONDA_SH to the path of your conda.sh file."
    exit 1
fi

echo ""
echo "🔍  Found Conda at: $CONDA_SH"

# ----------------------------------------------------------
#  Create the autostart directory & desktop entry
# ----------------------------------------------------------
mkdir -p "$HOME/.config/autostart"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=ScrobbleDaddy
Comment=Auto-scrobble vinyl to Last.fm
Exec=/bin/bash -c "sleep 10 && source $CONDA_SH && conda activate ScrobbleDaddyPy && cd $SCRIPT_DIR && python ScrobbleDaddy.py"
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "✅  Auto-start enabled!"
echo ""
echo "    ScrobbleDaddy will now launch automatically every time"
echo "    your Raspberry Pi boots up."
echo ""
echo "    To test it, reboot your Pi:"
echo ""
echo "        sudo reboot"
echo ""
echo "    To disable auto-start later, run:"
echo ""
echo "        bash $SCRIPT_DIR/setup_autostart.sh --remove"
echo ""
