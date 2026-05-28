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
    alsa-utils \
    wget

print_success "System dependencies installed."


# ----------------------------------------------------------
#  Step 2: Miniforge
# ----------------------------------------------------------
print_step 2 "Setting up Miniforge..."

CONDA_DIR=""
for path in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/mambaforge"; do
    if [ -d "$path/bin" ]; then
        CONDA_DIR="$path"
        break
    fi
done

if [ -n "$CONDA_DIR" ]; then
    print_skip "Found conda at: $CONDA_DIR"
else
    echo "    Downloading Miniforge..."

    ARCH=$(uname -m)
    wget -q --show-progress \
        "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-${ARCH}.sh" \
        -O /tmp/miniforge.sh
    bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
    rm /tmp/miniforge.sh

    CONDA_DIR="$HOME/miniforge3"
    print_success "Miniforge installed."
fi

CONDA="$CONDA_DIR/bin/conda"
PIP="$CONDA_DIR/envs/$ENV_NAME/bin/pip"
PYTHON="$CONDA_DIR/envs/$ENV_NAME/bin/python"


# ----------------------------------------------------------
#  Step 3: Python Environment
# ----------------------------------------------------------
print_step 3 "Creating $ENV_NAME environment..."

# Remove if exists
if [ -d "$CONDA_DIR/envs/$ENV_NAME" ]; then
    echo "    Removing old environment..."
    "$CONDA" env remove -n "$ENV_NAME" -y 2>/dev/null || rm -rf "$CONDA_DIR/envs/$ENV_NAME"
fi

echo "    Creating Python 3.9 environment..."
"$CONDA" create -n "$ENV_NAME" python=3.9 -y -q

echo "    Installing packages..."
"$PIP" install --quiet -r "$SCRIPT_DIR/requirements.txt"

print_success "Environment ready."


# ----------------------------------------------------------
#  Step 4: Last.fm Configuration
# ----------------------------------------------------------
print_step 4 "Configuring Last.fm..."

CURRENT_USERNAME=$("$PYTHON" -c "import json; print(json.load(open('$CONFIG_FILE'))['lastfm']['username'])" 2>/dev/null || echo "")

if [ -n "$CURRENT_USERNAME" ]; then
    echo ""
    echo "    Last.fm is already configured for user: $CURRENT_USERNAME"
    read -p "    Reconfigure? (y/N): " RECONFIG
    if [[ ! "$RECONFIG" =~ ^[Yy]$ ]]; then
        print_skip "Keeping existing config."
        SKIP_LASTFM=true
    fi
fi

if [ "$SKIP_LASTFM" != "true" ]; then
    echo ""
    echo "    Enter your Last.fm credentials to enable scrobbling."
    echo "    (Leave blank to skip — you can edit config.json later)"
    echo ""

    read -p "    Last.fm Username: " LASTFM_USER
    read -sp "    Last.fm Password: " LASTFM_PASS
    echo ""

    "$PYTHON" << PYEOF
import json
with open("$CONFIG_FILE", "r") as f:
    config = json.load(f)
config["lastfm"]["username"] = """$LASTFM_USER"""
config["lastfm"]["password"] = """$LASTFM_PASS"""
with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=4)
    f.write("\n")
PYEOF

    print_success "Last.fm saved to config.json"
fi


# ----------------------------------------------------------
#  Step 5: ALSA Audio Config
# ----------------------------------------------------------
print_step 5 "Configuring audio input..."

USB_CARD=$(arecord -l 2>/dev/null | grep -i "usb\|mic" | head -1 | grep -oP 'card \K[0-9]+')

if [ -z "$USB_CARD" ]; then
    echo ""
    echo "    Audio devices:"
    arecord -l 2>/dev/null | sed 's/^/    /' || echo "    (none found)"
    echo ""
    read -p "    Enter your mic's card number: " USB_CARD
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
    print_success "ALSA configured (USB mic card $USB_CARD, shared access)"
else
    print_info "No mic detected. Edit ~/.asoundrc later."
fi


# ----------------------------------------------------------
#  Step 6: Auto-Start
# ----------------------------------------------------------
print_step 6 "Auto-start configuration..."

read -p "    Start ScrobbleDaddy on boot? (Y/n): " AUTOSTART
AUTOSTART=${AUTOSTART:-Y}

if [[ "$AUTOSTART" =~ ^[Yy]$ ]]; then
    bash "$SCRIPT_DIR/setup_autostart.sh"
else
    print_skip "Skipping. Run setup_autostart.sh later."
fi


# =============================================================
echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     🎉  Installation Complete!  🎉     ║"
echo "  ╚═══════════════════════════════════════╝"
echo -e "${NC}"
echo "  To start ScrobbleDaddy:"
echo ""
echo "      bash run.sh"
echo ""
echo "  Put on a record and enjoy! 🎶"
echo ""
