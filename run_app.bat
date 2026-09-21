@echo off
setlocal enabledelayedexpansion
title Messaging Artifact Reconstructor — Launcher

echo =====================================================
echo   MESSAGING ARTIFACT RECONSTRUCTOR
echo   Forensic Analysis Platform v1.0
echo =====================================================
echo.

:: ── Find Python ──────────────────────────────────────
set PYTHON_DIR=
set PYTHON_EXE=
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python312"
    "%LOCALAPPDATA%\Programs\Python\Python311"
    "%LOCALAPPDATA%\Programs\Python\Python310"
    "%LOCALAPPDATA%\Programs\Python\Python39"
    "C:\Python312"
    "C:\Python311"
    "C:\Python310"
    "C:\Program Files\Python312"
    "C:\Program Files\Python311"
) do (
    if exist "%%~p\python.exe" (
        set PYTHON_DIR=%%~p
        set PYTHON_EXE=%%~p\python.exe
        goto :found_python
    )
)
:: Try the global PATH
where python >nul 2>&1
if %ERRORLEVEL%==0 (
    set PYTHON_EXE=python
    goto :found_python
)
echo [ERROR] Python not found! Please install Python from https://python.org
pause
exit /b 1
:found_python
echo [OK] Found Python: %PYTHON_EXE%

:: ── Find Node / npm ───────────────────────────────────
set NODE_DIR=
set NPM_EXE=
for %%p in (
    "C:\Program Files\nodejs"
    "C:\Program Files (x86)\nodejs"
    "%APPDATA%\npm"
    "%ProgramFiles%\nodejs"
) do (
    if exist "%%~p\npm.cmd" (
        set NODE_DIR=%%~p
        set NPM_EXE=%%~p\npm.cmd
        goto :found_npm
    )
)
where npm >nul 2>&1
if %ERRORLEVEL%==0 ( set NPM_EXE=npm && goto :found_npm )
echo [ERROR] Node.js / npm not found! Please install from https://nodejs.org
pause
exit /b 1
:found_npm
echo [OK] Found npm: %NPM_EXE%
echo.

:: ── Stop only this app's previous windows ─────────────────
:: This prevents a second launch from silently leaving an old backend on port 8000.
taskkill /FI "WINDOWTITLE eq BACKEND — FastAPI" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq FRONTEND — Vite" /T /F >nul 2>&1

:: ── Update PATH temporarily ───────────────────────────
:: This ensures that spawned processes (like npm post-install scripts) can find node and python
if defined PYTHON_DIR (
    set "PATH=%PYTHON_DIR%;%PYTHON_DIR%\Scripts;!PATH!"
)
if defined NODE_DIR (
    set "PATH=%NODE_DIR%;!PATH!"
)

:: ── Install backend dependencies ─────────────────────
echo [1/4] Installing backend Python dependencies...
"%PYTHON_EXE%" -m pip install -r backend\requirements.txt --quiet
if %ERRORLEVEL% neq 0 (
    echo [WARN] pip install had warnings, continuing...
)
echo [OK] Backend dependencies ready.
echo.

:: ── Install frontend dependencies ────────────────────
echo [2/4] Installing frontend Node dependencies...
pushd frontend
call "%NPM_EXE%" install --silent
popd
echo [OK] Frontend dependencies ready.
echo.

:: ── Start Backend ─────────────────────────────────────
echo [3/4] Starting FastAPI backend on http://localhost:8000 ...
start "BACKEND — FastAPI" cmd /k "cd /d "%~dp0backend" && set "PATH=!PATH!" && "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul

:: ── Start Frontend ────────────────────────────────────
echo [4/4] Starting React frontend on http://localhost:5173 ...
start "FRONTEND — Vite" cmd /k "cd /d "%~dp0frontend" && set "PATH=!PATH!" && "%NPM_EXE%" run dev"

echo.
echo =====================================================
echo   BOTH SERVERS ARE STARTING UP!
echo.
echo   Dashboard:  http://localhost:5173
echo   API Docs:   http://localhost:8000/api/docs
echo.
echo   This window can be closed.
echo   Close the two black CMD windows to stop the app.
echo =====================================================
echo.
timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
