@echo off
echo ==========================================================
echo Installing MCP Visual Paradigm Plugin...
echo ==========================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0plugin\build.ps1" -Deploy

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================================
    echo SUCCESS: Plugin installed!
    echo Restart Visual Paradigm to see the MCP ribbon tab.
    echo ==========================================================
) else (
    echo.
    echo [ERROR] Installation failed. Please ensure PowerShell is enabled.
)
pause
