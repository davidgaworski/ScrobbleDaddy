#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Auto-Start Setup Script
# =============================================================

DESKTOP_FILE="$HOME/.config/autostart/scrobbledaddy.desktop"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "--remove" ]; then
    if [ -f "$DESKTOP_FILE" ]; then
        rm "$DESKTOP_FILE"
        echo "✅  Auto-start disabled."
    else
        echo "ℹ️   Auto-start was not enabled."
    fi
    exit 0
fi

# Find conda path
CONDA_SH=""
for path in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -f "$path/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$path/etc/profile.d/conda.sh"
        break
    fi
done

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
echo "    Reboot to test: sudo reboot"
echo "    To disable: bash $SCRIPT_DIR/setup_autostart.sh --remove"
echo ""
