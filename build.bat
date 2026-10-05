@echo off
rem Build dist\SlidePrint.exe locally in a clean virtual environment (needs Python 3.12 on PATH).
cd /d "%~dp0"
if not exist .venv python -m venv .venv || goto :error
.venv\Scripts\python -m pip install -q -r requirements.txt -r requirements-build.txt || goto :error
.venv\Scripts\python test_dedup_slides.py || goto :error
.venv\Scripts\python -m PyInstaller --onefile --windowed --noconfirm --name SlidePrint --add-data "LICENSE;." --add-data "THIRD_PARTY_NOTICES.txt;." --add-data "ui.html;." slideprint_gui.py || goto :error
echo.
echo Built dist\SlidePrint.exe
exit /b 0
:error
echo Build failed.
exit /b 1
