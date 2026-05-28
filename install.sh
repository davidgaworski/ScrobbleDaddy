#!/bin/bash
# =============================================================
#  ScrobbleDaddy - Full Installation Script
#
#  Installs everything you need to run ScrobbleDaddy on a
#  Raspberry Pi. Just run this after cloning the repo:
#
#    bash install.sh
#
# =============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
ENV_NAME="ScrobbleDaddyPy"

# ----------------------------------------------------------
#  Colors for pretty output
# ----------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

print_step()    { echo -e "\n${BLUE}${BOLD}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"; }
print_success() { echo -e "    ${GREEN}✅  $1${NC}"; }
print_skip()    { echo -e "    ${YELLOW}⏭️   $1${NC}"; }
print_error()   { echo -e "    ${RED}❌  $1${NC}"; }
print_info()    { echo -e "    ${YELLOW}ℹ️   $1${NC}"; }

TOTAL_STEPS=6

# =============================================================
echo -e "${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║       🎶 ScrobbleDaddy Installer       ║"
echo "  ║     Vinyl → Shazam → Last.fm           ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"
# =============================================================


# ----------------------------------------------------------
#  Step 1: System Dependencies
# ----------------------------------------------------------
print_step 1 "Installing system dependencies..."

sudo apt update -y
sudo apt install -y \
    git \
    portaudio19-dev \
    libsdl2-dev \
    libsdl2-mixer-dev \
    libsdl2-image-dev \
    libsdl2-ttf-dev \
    libsndfile1-dev \
    ffmpeg \
    alsa-utils

print_success "System dependencies installed."


# ----------------------------------------------------------
#  Step 2: Miniforge (conda for ARM)
# ----------------------------------------------------------
print_step 2 "Setting up Miniforge..."

CONDA_SH=""
for path in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -f "$path/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$path/etc/profile.d/conda.sh"
        break
    fi
done

if [ -n "$CONDA_SH" ]; then
    print_skip "Conda already installed at: $CONDA_SH"
else
    echo ""
    echo "    Downloading Miniforge (this may take a few minutes)..."
    echo ""

    ARCH=$(uname -m)
    FORGE_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${ARCH}.sh"

    wget -q --show-progress "$FORGE_URL" -O /tmp/miniforge_installer.sh
    bash /tmp/miniforge_installer.sh -b -p "$HOME/miniforge3"
    rm /tmp/miniforge_installer.sh

    CONDA_SH="$HOME/miniforge3/etc/profile.d/conda.sh"
    print_success "Miniforge installed."
fi

# Activate conda
source "$CONDA_SH"

# Make conda available permanently
"$(dirname "$(dirname "$CONDA_SH")")/bin/conda" init bash 2>/dev/null || true
print_success "Conda added to your shell."


# ----------------------------------------------------------
#  Step 3: Conda Environment (Python 3.9)
# ----------------------------------------------------------
print_step 3 "Creating the $ENV_NAME environment..."

# Remove existing environment if present
if conda env list | grep -q "$ENV_NAME"; then
    echo "    Removing existing environment..."
    conda env remove -n "$ENV_NAME" -y
fi

echo ""
echo "    Creating Python 3.9 environment and installing packages..."
echo "    (this may take several minutes)"
echo ""

conda create -n "$ENV_NAME" python=3.9 -y
conda run -n "$ENV_NAME" pip install -r "$SCRIPT_DIR/requirements.txt"
print_success "Conda environment created."


# ----------------------------------------------------------
#  Step 4: Last.fm Configuration
# ----------------------------------------------------------
print_step 4 "Configuring Last.fm..."

CURRENT_USERNAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['lastfm']['username'])" 2>/dev/null || echo "")

if [ -n "$CURRENT_USERNAME" ]; then
    echo ""
    echo "    Last.fm is already configured for user: $CURRENT_USERNAME"
    echo ""
    read -p "    Do you want to reconfigure? (y/N): " RECONFIG
    if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
        print_skip "Keeping existing Last.fm configuration."
        SKIP_LASTFM=true
    fi
fi

if [ "$SKIP_LASTFM" != "true" ]; then
    echo ""
    echo "    You'll need a Last.fm account and API key."
    echo "    Get your API key here: https://www.last.fm/api/account/create"
    echo "    (Leave blank to skip — you can configure later in config.json)"
    echo ""

    read -p "    Last.fm Username: " LASTFM_USER
    read -sp "    Last.fm Password: " LASTFM_PASS
    echo ""
    read -p "    API Key:          " LASTFM_KEY
    read -p "    API Secret:       " LASTFM_SECRET

    if [ -z "$LASTFM_USER" ] || [ -z "$LASTFM_PASS" ] || [ -z "$LASTFM_KEY" ] || [ -z "$LASTFM_SECRET" ]; then
        print_info "Some fields were left blank. You can fill them in later by editing config.json"
    fi

    python3 << PYEOF
import json

with open("$CONFIG_FILE", "r") as f:
    config = json.load(f)

config["lastfm"]["username"] = """$LASTFM_USER"""
config["lastfm"]["password"] = """$LASTFM_PASS"""
config["lastfm"]["api_key"] = """$LASTFM_KEY"""
config["lastfm"]["api_secret"] = """$LASTFM_SECRET"""

with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=4)
    f.write("\n")
PYEOF

    print_success "Last.fm credentials saved to config.json"
fi


# ----------------------------------------------------------
#  Step 5: Audio Device Setup (ALSA config)
# ----------------------------------------------------------
print_step 5 "Configuring audio input..."

# Auto-detect USB mic card number
USB_CARD=$(arecord -l 2>/dev/null | grep -i "usb\|mic" | head -1 | grep -oP 'card \K[0-9]+')

if [ -z "$USB_CARD" ]; then
    echo ""
    echo "    Available audio devices:"
    arecord -l 2>/dev/null | sed 's/^/    /'
    echo ""
    read -p "    Enter your microphone's card number: " USB_CARD
fi

if [ -n "$USB_CARD" ]; then
    cat > "$HOME/.asoundrc" << ASOUNDEOF
pcm.!default {
    type asym
    playback.pcm "plughw:0,0"
    capture.pcm "plug:shared_mic"
}

pcm.shared_mic {
    type dsnoop
    ipc_key 816357
    slave {
        pcm "hw:${USB_CARD},0"
        channels 1
    }
}
ASOUNDEOF
    print_success "ALSA configured — USB mic (card $USB_CARD) with shared access"
else
    print_info "No USB mic detected. You can configure later by editing ~/.asoundrc"
fi


# ----------------------------------------------------------
#  Step 6: Auto-Start Setup
# ----------------------------------------------------------
print_step 6 "Auto-start configuration..."

echo ""
read -p "    Would you like ScrobbleDaddy to start automatically on boot? (Y/n): " AUTOSTART
AUTOSTART=${AUTOSTART:-Y}

if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
    bash "$SCRIPT_DIR/setup_autostart.sh"
else
    print_skip "Skipping auto-start. You can set it up later with: bash setup_autostart.sh"
fi


# =============================================================
#  Done!
# =============================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     🎉  Installation Complete!  🎉     ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"
echo "  To start ScrobbleDaddy right now:"
echo ""
echo "      bash run.sh"
echo ""
echo "  Put on a record and enjoy! 🎶"
echo ""
