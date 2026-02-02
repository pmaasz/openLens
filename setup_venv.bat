@echo off
REM openlens Setup Script for Windows
REM Automates the virtual environment setup process

echo ========================================================================
echo                                                                        
echo              openlens - Virtual Environment Setup
echo                                                                        
echo ========================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.6 or higher from python.org
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%
echo.

REM Check if venv already exists
if exist venv (
    echo Virtual environment 'venv' already exists
    set /p RECREATE="Remove and recreate? (y/N): "
    if /i "%RECREATE%"=="y" (
        echo Removing existing venv...
        rmdir /s /q venv
    ) else (
        echo Keeping existing venv
        echo.
        echo To activate the existing venv, run:
        echo    venv\Scripts\activate
        pause
        exit /b 0
    )
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

if not exist venv (
    echo Error: Failed to create virtual environment
    pause
    exit /b 1
)

echo Virtual environment created
echo.

REM Activate and verify
echo Verifying installation...
call venv\Scripts\activate.bat

where python
echo Virtual environment activated
echo.

REM Check tkinter
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo Warning: tkinter is not available
    echo GUI may not work properly
) else (
    echo tkinter is available (GUI will work)
)

call deactivate

echo.
echo ========================================================================
echo Setup Complete!
echo ========================================================================
echo.
echo To activate the virtual environment:
echo    venv\Scripts\activate
echo.
echo To run the application:
echo    python lens_editor_gui.py    (GUI version)
echo    python lens_editor.py        (CLI version)
echo.
echo To run tests:
echo    python tests/run_all_tests.py
echo.
echo To deactivate when done:
echo    deactivate
echo.
pause
