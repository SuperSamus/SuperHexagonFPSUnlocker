@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
python -m superhexagon_fps_unlocker %*
if errorlevel 1 pause

