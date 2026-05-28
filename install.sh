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
    wget

print_success "System dependencies installed."


# ----------------------------------------------------------
#  Step 2: Miniconda
# ----------------------------------------------------------
print_step 2 "Setting up Miniconda..."

CONDA_SH=""
for path in "$HOME/miniconda3" "$HOME/miniforge3" "$HOME/anaconda3" "$HOME/mambaforge"; do
    if [ -f "$path/etc/profile.d/conda.sh" ]; then
        CONDA_SH="$path/etc/profile.d/conda.sh"
        break
    fi
done

if [ -n "$CONDA_SH" ]; then
    print_skip "Conda already installed at: $CONDA_SH"
else
    echo ""
    echo "    Downloading Miniconda (this may take a few minutes)..."
    echo ""

    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "aarch64" ]; then
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
    elif [ "$ARCH" = "x86_64" ]; then
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    elif [ "$ARCH" = "armv7l" ]; then
        MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-armv7l.sh"
    else
        print_error "Unsupported architecture: $ARCH"
        exit 1
    fi

    wget -q --show-progress "$MINICONDA_URL" -O /tmp/miniconda_installer.sh
    bash /tmp/miniconda_installer.sh -b -p "$HOME/miniconda3"
    rm /tmp/miniconda_installer.sh

    CONDA_SH="$HOME/miniconda3/etc/profile.d/conda.sh"
    print_success "Miniconda installed."
fi

# Activate conda for the rest of the script
source "$CONDA_SH"

# Make conda available permanently
"$(dirname "$(dirname "$CONDA_SH")")/bin/conda" init bash 2>/dev/null
print_success "Conda added to your shell (takes effect on next login)."


# ----------------------------------------------------------
#  Step 3: Conda Environment
# ----------------------------------------------------------
print_step 3 "Creating the ScrobbleDaddyPy environment..."

# Remove existing environment if present
if conda env list | grep -q "ScrobbleDaddyPy"; then
    echo "    Removing existing environment..."
    conda env remove -n ScrobbleDaddyPy -y
fi

echo ""
echo "    Creating Python environment and installing packages..."
echo "    (this may take several minutes)"
echo ""

conda create -n ScrobbleDaddyPy python=3.11 -y
conda run -n ScrobbleDaddyPy pip install -r "$SCRIPT_DIR/requirements.txt"
print_success "Conda environment created."


# ----------------------------------------------------------
#  Step 4: Last.fm Configuration
# ----------------------------------------------------------
print_step 4 "Configuring Last.fm..."

# Check if credentials are already filled in
CURRENT_USERNAME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['lastfm']['username'])")

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
    echo ""

    read -p "    Last.fm Username: " LASTFM_USER
    read -sp "    Last.fm Password: " LASTFM_PASS
    echo ""
    read -p "    API Key:          " LASTFM_KEY
    read -p "    API Secret:       " LASTFM_SECRET

    if [ -z "$LASTFM_USER" ] || [ -z "$LASTFM_PASS" ] || [ -z "$LASTFM_KEY" ] || [ -z "$LASTFM_SECRET" ]; then
        print_info "Some fields were left blank. You can fill them in later by editing config.json"
    fi

    # Update config.json using Python (safe JSON handling)
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
#  Step 5: Audio Device Setup
# ----------------------------------------------------------
print_step 5 "Detecting audio devices..."

conda activate ScrobbleDaddyPy

echo ""
python -c "
import sounddevice as sd
devices = sd.query_devices()
print('    Available audio devices:')
print('    ─────────────────────────────────────────')
for i, d in enumerate(devices):
    marker = '  '
    if d['max_input_channels'] > 0:
        marker = '🎤'
    print(f'      {marker} [{i}] {d[\"name\"]} (inputs: {d[\"max_input_channels\"]})')
print('    ─────────────────────────────────────────')
print()
print('    Look for your USB microphone in the list above.')
print('    Devices marked with 🎤 can record audio.')
" 2>/dev/null || echo "    (Could not list audio devices — make sure your mic is plugged in)"

echo ""

CURRENT_DEVICE=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['audio']['device_index'])")

read -p "    Enter your microphone's device number [$CURRENT_DEVICE]: " DEVICE_INDEX
DEVICE_INDEX=${DEVICE_INDEX:-$CURRENT_DEVICE}

python3 << PYEOF
import json

with open("$CONFIG_FILE", "r") as f:
    config = json.load(f)

config["audio"]["device_index"] = int($DEVICE_INDEX)

with open("$CONFIG_FILE", "w") as f:
    json.dump(config, f, indent=4)
    f.write("\n")
PYEOF

print_success "Audio device set to index $DEVICE_INDEX"


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
echo "      conda activate ScrobbleDaddyPy"
echo "      python ScrobbleDaddy.py"
echo ""
echo "  Put on a record and enjoy! 🎶"
echo ""
