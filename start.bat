@echo off
title Arbitrage Launcher
color 0A

echo ===================================================
echo     ARBITRAGE CALCULATOR INITIALIZATION SEQUENCE
echo ===================================================
echo.

echo [1/5] Terminating any ghost background processes...
:: Use PowerShell WMI to surgically kill ONLY the CMD windows launched by this script
powershell -NoProfile -Command "Get-WmiObject Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and $_.CommandLine -match 'title Arbitrage' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Also kill python processes gracefully if they survived
powershell -NoProfile -Command "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match 'backend.main' -or $_.CommandLine -match 'run_engine.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

:: Kill by port - catches any remaining server processes
echo Clearing ports 5000 and 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 "') do if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 "') do if not "%%a"=="0" taskkill /F /PID %%a >nul 2>&1

:: Kill ngrok
taskkill /F /IM ngrok.exe >nul 2>&1

timeout /t 3 /nobreak >nul

echo [2/5] Ensuring python dependencies are up to date...
cd /d "%~dp0"
call .venv\Scripts\pip install requests httpx fastapi uvicorn aiohttp aiosqlite >nul 2>&1

echo [3/5] Booting up React Dashboard and API (Port 5000)...
start "Arbitrage Dashboard" cmd /k "title Arbitrage Dashboard && echo --- DASHBOARD BOOTING --- && npm run dev"

timeout /t 5 /nobreak >nul

echo [4/5] Booting up AI Semantic Matcher (Port 8000)...
start "Arbitrage Matcher" cmd /k "title Arbitrage Matcher && echo --- ML MATCHER BOOTING --- && .venv\Scripts\python -m backend.main"

timeout /t 4 /nobreak >nul

echo [5/5] Booting up Real-time Arb Engine...
start "Arbitrage Engine" cmd /k "title Arbitrage Engine && echo --- ARB ENGINE BOOTING --- && .venv\Scripts\python run_engine.py"

timeout /t 2 /nobreak >nul

echo Booting up Ngrok Tunnel for Cloud GPU...
start "Arbitrage Ngrok" cmd /k "title Arbitrage Ngrok && echo --- NGROK BOOTING --- && npx ngrok http 8000 --domain copyrightable-pseudocartilaginous-sade.ngrok-free.dev"

timeout /t 8 /nobreak >nul

echo Opening dashboard in browser...
start "" "http://localhost:5000/sentinel"

echo.
echo ===================================================
echo     ALL SYSTEMS ONLINE! (4 WORKER WINDOWS)
echo ===================================================
echo.
echo Dashboard:     http://localhost:5000
echo ML API:        http://localhost:8000
echo Arb Engine:    (Active continuous loop)
echo Cloud Tunnel:  https://copyrightable-pseudocartilaginous-sade.ngrok-free.dev
echo.
echo You can now safely close this launcher window (or keep it as the 4th window).
echo.
pause >nul
