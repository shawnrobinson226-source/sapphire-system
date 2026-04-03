# Sapphire AI — Windows Installer (PowerShell)
# One-liner: irm https://raw.githubusercontent.com/ddxfish/sapphire/main/install/install.ps1 | iex
$ErrorActionPreference = "Stop"

$SAPPHIRE_DIR = "$env:USERPROFILE\sapphire"
$CONDA_ENV = "sapphire"
$REPO = "https://github.com/ddxfish/sapphire.git"
$LAUNCHER = "$env:USERPROFILE\sapphire.bat"

function Info($msg)  { Write-Host "[Sapphire] $msg" -ForegroundColor Green }
function Warn($msg)  { Write-Host "[Sapphire] $msg" -ForegroundColor Yellow }
function Fail($msg)  { Write-Host "[Sapphire] $msg" -ForegroundColor Red; exit 1 }

# Find conda — check common locations
function Find-Conda {
    # Already on PATH?
    if (Get-Command conda -ErrorAction SilentlyContinue) { return "conda" }

    # Common install locations
    $paths = @(
        "$env:USERPROFILE\miniconda3\condabin\conda.bat",
        "$env:USERPROFILE\anaconda3\condabin\conda.bat",
        "$env:USERPROFILE\Miniconda3\condabin\conda.bat",
        "$env:USERPROFILE\Anaconda3\condabin\conda.bat",
        "C:\ProgramData\miniconda3\condabin\conda.bat",
        "C:\ProgramData\Miniconda3\condabin\conda.bat"
    )
    foreach ($p in $paths) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# ── Upgrade path ─────────────────────────────────────────────
if (Test-Path "$SAPPHIRE_DIR\.git") {
    Warn "Sapphire is already installed at $SAPPHIRE_DIR"
    $reply = Read-Host "Upgrade? (Y/n)"

    if ($reply -eq 'n' -or $reply -eq 'N') {
        Info "Run Sapphire anytime: ~\sapphire.bat"
        exit 0
    }

    Set-Location $SAPPHIRE_DIR
    git pull
    if ($LASTEXITCODE -ne 0) { Fail "git pull failed" }

    $conda = Find-Conda
    if (-not $conda) { Fail "Could not find conda" }
    & $conda run -n $CONDA_ENV pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }

    Info "Sapphire upgraded!"
    Info "Run: ~\sapphire.bat"
    exit 0
}

# ── Fresh install ────────────────────────────────────────────
Write-Host ""
Write-Host "  +===================================+" -ForegroundColor Green
Write-Host "  |     Sapphire AI - Installing      |" -ForegroundColor Green
Write-Host "  +===================================+" -ForegroundColor Green
Write-Host ""
Warn "This will download ~3-4GB of dependencies. Grab coffee."
Write-Host ""

# Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Info "Installing Git via winget..."
    winget install Git.Git --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Fail "Git install failed" }
    # Add to PATH for this session
    $env:PATH = "$env:ProgramFiles\Git\cmd;$env:PATH"
}

# Miniconda
$conda = Find-Conda
if (-not $conda) {
    Info "Installing Miniconda via winget..."
    winget install Anaconda.Miniconda3 --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) { Fail "Miniconda install failed" }

    # Init conda for PowerShell and CMD
    $condaBat = "$env:USERPROFILE\miniconda3\condabin\conda.bat"
    if (-not (Test-Path $condaBat)) {
        $condaBat = "$env:USERPROFILE\Miniconda3\condabin\conda.bat"
    }
    if (Test-Path $condaBat) {
        & $condaBat init powershell 2>$null
        & $condaBat init cmd.exe 2>$null
        Info "Miniconda installed and initialized."
    } else {
        Fail "Miniconda installed but conda.bat not found. Close and reopen terminal, then re-run."
    }

    # Refresh for this session
    $env:PATH = "$env:USERPROFILE\miniconda3\condabin;$env:USERPROFILE\miniconda3\Scripts;$env:PATH"
    $conda = Find-Conda
    if (-not $conda) { Fail "Conda not found after install. Close and reopen terminal, then re-run." }
}

# Clone
Info "Cloning Sapphire..."
git clone $REPO $SAPPHIRE_DIR
if ($LASTEXITCODE -ne 0) { Fail "git clone failed" }

# Conda environment
Info "Creating conda environment (python 3.11)..."
& $conda create -n $CONDA_ENV python=3.11 -y
if ($LASTEXITCODE -ne 0) { Fail "Failed to create conda env" }
& $conda activate $CONDA_ENV

# Python deps
Info "Installing Python dependencies (this takes a while)..."
& $conda run -n $CONDA_ENV pip install -r "$SAPPHIRE_DIR\requirements.txt"
if ($LASTEXITCODE -ne 0) { Fail "pip install failed" }

# Launcher .bat
$batContent = @"
@echo off
call conda activate sapphire
cd /d %USERPROFILE%\sapphire
python main.py
"@
Set-Content -Path $LAUNCHER -Value $batContent -Encoding ASCII
Info "Created launcher at $LAUNCHER"

# Done
Write-Host ""
Write-Host "  +===================================+" -ForegroundColor Green
Write-Host "  |  Sapphire installed successfully   |" -ForegroundColor Green
Write-Host "  +===================================+" -ForegroundColor Green
Write-Host ""
Write-Host "  Run anytime:  ~\sapphire.bat"
Write-Host "  Web UI:       https://localhost:8073"
Write-Host ""

$reply = Read-Host "Launch Sapphire now? (Y/n)"
if ($reply -ne 'n' -and $reply -ne 'N') {
    & $LAUNCHER
}
