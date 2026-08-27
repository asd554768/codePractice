@echo off
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel% equ 0 (
    python "%~dp0pdf_merger_gui.py"
    if %errorlevel% neq 0 pause
    exit /b
)

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0pdf_merger_gui.py"
    if %errorlevel% neq 0 pause
    exit /b
)

echo [ERROR] Python is not found in PATH!
pause
