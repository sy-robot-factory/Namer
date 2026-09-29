@echo off
cd /d "%~dp0"
uv run pyinstaller --noconfirm namer.spec
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)
echo.
echo Done: dist\Namer.exe
explorer dist
pause
