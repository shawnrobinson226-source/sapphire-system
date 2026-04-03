#!/bin/bash
# Sapphire AI — Linux Installer
# One-liner: curl -sL https://raw.githubusercontent.com/ddxfish/sapphire/main/install/install.sh | bash
set -e

SAPPHIRE_DIR="$HOME/sapphire"
CONDA_ENV="sapphire"
REPO="https://github.com/ddxfish/sapphire.git"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[Sapphire]${NC} $1"; }
warn()  { echo -e "${YELLOW}[Sapphire]${NC} $1"; }
fail()  { echo -e "${RED}[Sapphire]${NC} $1"; exit 1; }

# ── Upgrade path ─────────────────────────────────────────────
if [ -d "$SAPPHIRE_DIR/.git" ]; then
    warn "Sapphire is already installed at $SAPPHIRE_DIR"
    read -p "Upgrade? (Y/n) " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Nn]$ ]]; then
        info "Run Sapphire anytime: ~/sapphire.sh"
        exit 0
    fi

    cd "$SAPPHIRE_DIR"

    # Check for local changes
    if ! git diff --quiet 2>/dev/null; then
        warn "You have local changes. Stashing them before pull..."
        git stash
    fi

    git pull || fail "git pull failed — check your network connection"

    # Activate conda in this script's shell
    if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    fi
    conda activate "$CONDA_ENV" 2>/dev/null || fail "Could not activate conda env '$CONDA_ENV'"
    pip install -r requirements.txt

    info "Sapphire upgraded!"
    info "Run: ~/sapphire.sh"
    exit 0
fi

# ── Fresh install ────────────────────────────────────────────
echo ""
echo -e "${GREEN}  ╔═══════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║     Sapphire AI — Installing      ║${NC}"
echo -e "${GREEN}  ╚═══════════════════════════════════╝${NC}"
echo ""
warn "This will download ~3-4GB of dependencies. Grab coffee."
echo ""

# System deps
info "Installing system packages (may ask for sudo password)..."
sudo apt-get update -qq
sudo apt-get install -y libportaudio2 libsndfile1 git || fail "Failed to install system packages"

# Miniconda
if ! command -v conda &>/dev/null; then
    info "Installing Miniconda..."
    wget -q --show-progress https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh
    bash /tmp/miniconda.sh -b -p "$HOME/miniconda3" || fail "Miniconda install failed"
    rm -f /tmp/miniconda.sh
    "$HOME/miniconda3/bin/conda" init bash >/dev/null 2>&1
    info "Miniconda installed. Activating for this session..."
fi

# Source conda for this session (works whether just installed or already present)
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
else
    fail "Could not find conda. Please install Miniconda manually and re-run."
fi

# Clone
info "Cloning Sapphire..."
git clone "$REPO" "$SAPPHIRE_DIR" || fail "git clone failed"

# Conda environment
info "Creating conda environment (python 3.11)..."
conda create -n "$CONDA_ENV" python=3.11 -y || fail "Failed to create conda env"
conda activate "$CONDA_ENV"

# Python deps
info "Installing Python dependencies (this takes a while)..."
pip install -r "$SAPPHIRE_DIR/requirements.txt" || fail "pip install failed"

# Launcher script
cat > "$HOME/sapphire.sh" << 'LAUNCHER'
#!/bin/bash
# Sapphire AI launcher
if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
fi
conda activate sapphire
cd ~/sapphire
python main.py
LAUNCHER
chmod +x "$HOME/sapphire.sh"

# Done
echo ""
echo -e "${GREEN}  ╔═══════════════════════════════════╗${NC}"
echo -e "${GREEN}  ║   Sapphire installed successfully  ║${NC}"
echo -e "${GREEN}  ╚═══════════════════════════════════╝${NC}"
echo ""
echo "  Run anytime:  ~/sapphire.sh"
echo "  Web UI:       https://localhost:8073"
echo ""

read -p "Launch Sapphire now? (Y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    exec "$HOME/sapphire.sh"
fi
