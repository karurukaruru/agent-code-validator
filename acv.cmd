@echo off
chcp 65001 >nul
setlocal
set "ACV_ROOT=%~dp0"
set "ACV_PYTHON=%ACV_ROOT%.venv\Scripts\python.exe"
if exist "%ACV_PYTHON%" goto runtime_ready

set "ACV_PYTHON=%ACV_ROOT%..\acv_runtime\Scripts\python.exe"
if exist "%ACV_PYTHON%" goto runtime_ready

where python >nul 2>nul
if errorlevel 1 goto runtime_missing
set "ACV_PYTHON=python"
goto runtime_ready

:runtime_missing
echo Error: Python runtime was not found.
echo Create .venv in the ACV directory or install Python 3.10 or newer.
exit /b 1

:runtime_ready
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ACV_ROOT%;%PYTHONPATH%"
set "ACV_CONFIG=%ACV_ROOT%config.json"
set "ACV_OUTPUT_DIR=%ACV_ROOT%..\acv_outputs"

if not exist "%ACV_OUTPUT_DIR%" mkdir "%ACV_OUTPUT_DIR%"

"%ACV_PYTHON%" -m acv %*
exit /b %ERRORLEVEL%
