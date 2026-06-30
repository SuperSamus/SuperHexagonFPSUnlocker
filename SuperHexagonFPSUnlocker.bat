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
echo 2. Patch 240 Hz
echo 3. Patch 480 Hz
echo 4. Patch custom Hz
echo 5. Restore original
echo 6. Status
echo 0. Quit
echo.
choice /c 1234560 /n /m "Choose an option: "

if errorlevel 7 exit /b 0
if errorlevel 6 goto status
if errorlevel 5 goto restore
if errorlevel 4 goto patch_custom
if errorlevel 3 goto patch_480
if errorlevel 2 goto patch_240
if errorlevel 1 goto patch_120

:patch_120
python -m superhexagon_fps_unlocker patch --hz 120
goto done

:patch_240
python -m superhexagon_fps_unlocker patch --hz 240
goto done

:patch_480
python -m superhexagon_fps_unlocker patch --hz 480
goto done

:patch_custom
echo.
set "CUSTOM_HZ="
set /p "CUSTOM_HZ=Enter custom Hz (multiple of 60, minimum 120): "
if "%CUSTOM_HZ%"=="" goto menu
python -m superhexagon_fps_unlocker patch --hz "%CUSTOM_HZ%"
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
