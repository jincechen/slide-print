@echo off
rem Build dist\SlidePrint.exe locally in a clean virtual environment (needs Python 3.12 on PATH).
cd /d "%~dp0"
rem Icon set to ship: a folder in icons\ (cards or layers); see icons\make_assets.py
set ICONSET=layers
if not exist .venv python -m venv .venv || goto :error
.venv\Scripts\python -m pip install -q -r requirements.txt -r requirements-build.txt || goto :error
.venv\Scripts\python test_dedup_slides.py || goto :error
.venv\Scripts\python -m PyInstaller --onefile --windowed --splash icons\%ICONSET%\splash.png --manifest app.manifest --noconfirm --name SlidePrint --icon icons\%ICONSET%\icon.ico --add-data "LICENSE;." --add-data "THIRD_PARTY_NOTICES.txt;." --add-data "icons\%ICONSET%\icon.ico;." --add-data "icons\%ICONSET%\logo.png;." --add-data "ui.html;." slideprint_gui.py || goto :error
echo.
echo Built dist\SlidePrint.exe
exit /b 0
:error
echo Build failed.
exit /b 1
