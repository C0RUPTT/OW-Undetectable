@echo off
rem Gets the latest version. Your my_settings.json, models and history are kept.
cd /d "%~dp0"
git pull
if errorlevel 1 (
  echo.
  echo Update failed. Copy the text above and send it to Claude.
  pause
  exit /b 1
)
python -m pip install -q -r requirements.txt
echo.
echo Up to date.
pause
