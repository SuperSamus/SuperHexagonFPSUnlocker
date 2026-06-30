@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"

if not "%~1"=="" goto run_args

:menu
cls
echo SuperHexagonFPSUnlocker
echo.
echo 1. Patch 120 Hz
echo 2. Patch 180 Hz
echo 3. Patch 240 Hz
echo 4. Patch 300 Hz
echo 5. Patch 360 Hz
echo 6. Restore original
echo 7. Status
echo 0. Quit
echo.
choice /c 12345670 /n /m "Choose an option: "

if errorlevel 8 exit /b 0
if errorlevel 7 goto status
if errorlevel 6 goto restore
if errorlevel 5 goto patch_360
if errorlevel 4 goto patch_300
if errorlevel 3 goto patch_240
if errorlevel 2 goto patch_180
if errorlevel 1 goto patch_120

:patch_120
python -m superhexagon_fps_unlocker patch --hz 120
goto done

:patch_180
python -m superhexagon_fps_unlocker patch --hz 180
goto done

:patch_240
python -m superhexagon_fps_unlocker patch --hz 240
goto done

:patch_300
python -m superhexagon_fps_unlocker patch --hz 300
goto done

:patch_360
python -m superhexagon_fps_unlocker patch --hz 360
goto done

:restore
python -m superhexagon_fps_unlocker restore
goto done

:status
python -m superhexagon_fps_unlocker status
goto done

:run_args
python -m superhexagon_fps_unlocker %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%

:done
set "EXIT_CODE=%ERRORLEVEL%"
echo.
pause
exit /b %EXIT_CODE%
