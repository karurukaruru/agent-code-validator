@echo off
setlocal
cd /d "%~dp0"
set "PATCHCOURT_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PATCHCOURT_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist ".venv-dev\Scripts\python.exe" set "PATCHCOURT_PYTHON=%~dp0.venv-dev\Scripts\python.exe"
"%PATCHCOURT_PYTHON%" -m patchcourt.launcher
if errorlevel 1 (
  echo.
  echo Could not start PatchCourt. Python 3.10+ and a free port 8765 are required.
  pause
)
endlocal
