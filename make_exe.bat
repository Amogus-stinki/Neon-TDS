@echo off
setlocal
rem ======================================================================
rem  NEON BASTION  -  turns neon_bastion.py into NeonBastion.exe
rem  Put this file in the same folder as neon_bastion.py and double-click it.
rem  Your friends only need NeonBastion.exe - no Python needed on their PC.
rem ======================================================================
cd /d "%~dp0"
title NEON BASTION - making NeonBastion.exe
echo.
echo   ==== NEON BASTION : making NeonBastion.exe ====
echo.

if not exist "neon_bastion.py" goto :nofile

rem ---- find Python -------------------------------------------------------
set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY goto :nopython
echo Using Python:
%PY% --version
echo.

rem ---- tools: PyInstaller, and pygame if this Python does not have it ----
echo [1/3] Getting the build tools (needs internet the first time)...
%PY% -m pip install --disable-pip-version-check --upgrade pyinstaller
if errorlevel 1 goto :pipfail
%PY% -c "import pygame" >nul 2>&1
if errorlevel 1 (
    %PY% -m pip install --disable-pip-version-check pygame-ce
    if errorlevel 1 goto :pipfail
)
echo.

rem ---- build -------------------------------------------------------------
echo [2/3] Building NeonBastion.exe - this takes a minute or two...
if exist "NeonBastion.exe" del /q "NeonBastion.exe"
rem (the game file is packed inside too, so the .exe can hand its version to your other PC)
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed --name NeonBastion --add-data "neon_bastion.py;." neon_bastion.py
if errorlevel 1 goto :buildfail
if not exist "dist\NeonBastion.exe" goto :buildfail

rem ---- tidy up -----------------------------------------------------------
echo.
echo [3/3] Tidying up...
move /y "dist\NeonBastion.exe" "NeonBastion.exe" >nul
rmdir /s /q build >nul 2>&1
rmdir /s /q dist >nul 2>&1
del /q NeonBastion.spec >nul 2>&1

echo.
echo   ==========================================================
echo     DONE!  NeonBastion.exe is in this folder.
echo     Send just that file to your brother and friends.
echo     Their saves are kept next to the .exe on their own PC.
echo.
echo     UPDATING LATER: no need to run this again. Put a newer
echo     neon_bastion.py next to NeonBastion.exe and the .exe runs it.
echo   ==========================================================
echo.
explorer /select,"%~dp0NeonBastion.exe"
pause
exit /b 0

:nofile
echo Could not find neon_bastion.py.
echo Put make_exe.bat in the SAME folder as neon_bastion.py, then run it again.
pause
exit /b 1

:nopython
echo Python is not installed on this PC.
echo 1. Get it from https://www.python.org/downloads/
echo 2. In the installer, tick "Add python.exe to PATH".
echo 3. Run make_exe.bat again.
start "" https://www.python.org/downloads/
pause
exit /b 1

:pipfail
echo.
echo Could not download the build tools.
echo Check that the internet is on, then run make_exe.bat again.
pause
exit /b 1

:buildfail
echo.
echo The build did not finish. Scroll up to see the first error,
echo or send that text to Claude and ask what went wrong.
pause
exit /b 1
