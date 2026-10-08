@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PYTHON=py -3") else (set "PYTHON=python")
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python virtual environment...
  %PYTHON% -m venv .venv
  if errorlevel 1 (echo Python 3.10+ must be installed and on PATH. & pause & exit /b 1)
)
echo [2/3] Installing required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Package installation failed. Check internet connectivity. & pause & exit /b 1)
if not exist ".env" copy ".env.example" ".env" >nul
echo [3/3] Opening http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
echo Leave this window open while using PocketSmart AI.
".venv\Scripts\python.exe" app.py
pause
