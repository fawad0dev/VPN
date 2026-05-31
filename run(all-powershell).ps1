# ── VPN Client launcher — PowerShell (Windows / Linux / macOS) ───────────
# Works with Windows PowerShell 5.1+ and PowerShell Core 7+
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSDefaultParameterValues['*:Encoding'] = 'utf8'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

# ── Helpers ──────────────────────────────────────────────────────────────
function Write-Step { param($msg) Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Setup { param($msg) Write-Host "[SETUP] $msg" -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red }

# ── Detect platform ──────────────────────────────────────────────────────
$IsWin  = $PSVersionTable.PSEdition -eq 'Desktop' -or $IsWindows
$IsMac  = $IsMacOS
$IsLin  = $IsLinux

# ── Find Python 3.10+ ────────────────────────────────────────────────────
$PythonCmd = $null
foreach ($cmd in @('python3', 'python')) {
    try {
        $ver = & $cmd -c "import sys; print(sys.version_info >= (3,10))" 2>$null
        if ($ver -eq 'True') { $PythonCmd = $cmd; break }
    } catch {}
}

if (-not $PythonCmd) {
    Write-Err "Python 3.10+ is required but not found in PATH."
    if ($IsWin) {
        Write-Host "  Download from: https://www.python.org/downloads/"
        Write-Host "  Or via winget: winget install Python.Python.3.13"
    } elseif ($IsMac) {
        Write-Host "  Install via Homebrew: brew install python"
    } else {
        Write-Host "  Install via apt: sudo apt install python3 python3-venv python3-pip"
    }
    exit 1
}

Write-Step "Using Python: $(& $PythonCmd --version)"

# ── Venv paths ───────────────────────────────────────────────────────────
if ($IsWin) {
    $VenvPython = ".venv\Scripts\python.exe"
    $VenvPip    = ".venv\Scripts\pip.exe"
} else {
    $VenvPython = ".venv/bin/python"
    $VenvPip    = ".venv/bin/pip"
}

# ── Create venv if missing ───────────────────────────────────────────────
if (-not (Test-Path $VenvPython)) {
    Write-Setup "Creating virtual environment..."
    & $PythonCmd -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Err "Failed to create venv."; exit 1 }
}

# ── Install / upgrade deps ───────────────────────────────────────────────
Write-Setup "Checking dependencies..."
& $VenvPip install -q --upgrade pip
& $VenvPip install -q -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Err "Failed to install requirements."; exit 1 }

# ── Linux: warn about missing system Qt libs ─────────────────────────────
if ($IsLin) {
    $qtOk = & $VenvPython -c "from PyQt6.QtWidgets import QApplication" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[WARN]  PyQt6 import failed. Install system Qt deps:" -ForegroundColor Yellow
        Write-Host "        sudo apt install libxcb-cursor0 libgl1"
    }
}

# ── Launch ───────────────────────────────────────────────────────────────
Write-Step "Starting VPN Client..."
& $VenvPython main.py @args
$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host "`n[WARN]  App exited with code $code" -ForegroundColor Yellow
    if ($IsWin) { Read-Host "Press Enter to close" }
}
exit $code
