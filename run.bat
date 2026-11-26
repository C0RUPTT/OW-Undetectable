@echo off
rem Starts OW Assist with the model, mic and phone view from your settings.
cd /d "%~dp0"
python -m ow_assist %*
pause
