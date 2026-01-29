@echo off
echo ========================================
echo   CAPTIONEER STUDIO
echo   Professional Caption Editor
echo ========================================
echo.

REM Start API server
echo [1/2] Starting API server...
start "Captioneer API" cmd /k "cd /d %~dp0 && python -m api.server"

REM Wait for API to be ready
timeout /t 3 /nobreak > nul

REM Start frontend
echo [2/2] Starting Studio frontend...
cd studio
start "Captioneer Studio" cmd /k "npm run dev"

echo.
echo ========================================
echo   Studio is starting...
echo   
echo   API:     http://localhost:8000
echo   Studio:  http://localhost:5174
echo ========================================
echo.
echo Press any key to open Studio in browser...
pause > nul

start http://localhost:5174
