@echo off
cd /d "%~dp0"
python build_site.py
echo.
echo Done. Press any key to close.
pause >nul
