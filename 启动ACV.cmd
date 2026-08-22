@echo off
chcp 65001 >nul
setlocal
set "ACV_ROOT=%~dp0"
set "INTERACTIVE="

set "ACV_PYTHON=%ACV_ROOT%.venv\Scripts\python.exe"
if exist "%ACV_PYTHON%" goto runtime_ready

set "ACV_PYTHON=%ACV_ROOT%..\acv_runtime\Scripts\python.exe"
if exist "%ACV_PYTHON%" goto runtime_ready

where python >nul 2>nul
if errorlevel 1 goto runtime_missing
set "ACV_PYTHON=python"

:runtime_ready
if not "%~1"=="" goto argument_supplied

set "INTERACTIVE=1"
echo Enter the full path of the project to review.
echo Example: D:\code\my_project
set /p "PROJECT_PATH=Project path: "
if not defined PROJECT_PATH goto no_project
goto run_review

:argument_supplied
set "PROJECT_PATH=%~1"

:run_review
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ACV_ROOT%;%PYTHONPATH%"
set "ACV_CONFIG=%ACV_ROOT%config.json"
set "ACV_OUTPUT_DIR=%ACV_ROOT%..\acv_outputs"

if not exist "%ACV_OUTPUT_DIR%" mkdir "%ACV_OUTPUT_DIR%"

"%ACV_PYTHON%" -m acv review "%PROJECT_PATH%"
set "ACV_EXIT=%ERRORLEVEL%"
echo.
if "%ACV_EXIT%"=="0" goto review_ok
echo Review failed. Check the Error message above, config.json, and project path.
goto finish

:review_ok
echo Review complete.
echo Reports directory: %ACV_ROOT%..\acv_outputs
goto finish

:runtime_missing
echo Error: Python runtime was not found.
echo Create .venv in the ACV directory or install Python 3.10 or newer.
set "ACV_EXIT=1"
goto finish

:no_project
echo No project path was entered.
set "ACV_EXIT=1"

:finish
if defined INTERACTIVE pause
exit /b %ACV_EXIT%
