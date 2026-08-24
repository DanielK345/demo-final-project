@echo off
echo Starting AloSM Dev Environment...

:: Terminal 1: Backend
start "AloSM Backend" cmd /k "cd /d C:\Users\KHANH\Documents\GitHub\P-160 && .\.venv\Scripts\activate.bat && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"

:: Wait 2 seconds
timeout /t 2 /nobreak >nul

:: Terminal 2: Frontend
start "AloSM Frontend" cmd /k "cd /d C:\Users\KHANH\Documents\GitHub\P-160\src\frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
pause
