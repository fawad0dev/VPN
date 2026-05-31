@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title VPN Client

:: ── Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Download Python 3.10+ from https://www.python.org/downloads/
    pause & exit /b 1
)

:: ── Check / create venv ───────────────────────────────────────────────────
if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 ( echo [ERROR] Failed to create venv. & pause & exit /b 1 )
)

:: ── Install / upgrade dependencies ───────────────────────────────────────
echo [SETUP] Checking dependencies...
.venv\Scripts\pip install -q --upgrade pip
.venv\Scripts\pip install -q -r requirements.txt
if errorlevel 1 ( echo [ERROR] Failed to install requirements. & pause & exit /b 1 )

:: ── Launch ────────────────────────────────────────────────────────────────
echo [INFO]  Starting VPN Client...
.venv\Scripts\python main.py %*
set EXIT_CODE=%errorlevel%

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [WARN]  App exited with code %EXIT_CODE%
    pause
)
endlocal
