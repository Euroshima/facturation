@echo off
REM ==================================================
REM Build minimal de l'app Facturation (= celui qui fonctionnait).
REM psycopg2 est embarque par le hook automatique de PyInstaller.
REM Pas de --icon ni --version-file (ressource PE risquee).
REM ==================================================

echo [1/3] Nettoyage...
rmdir /s /q build dist 2>nul

echo [2/3] Dependances...
py -m pip install --upgrade pip >nul
py -m pip install -r requirements.txt >nul
py -m pip install pyinstaller >nul

echo [3/3] Compilation...
py -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --clean ^
    --paths=src ^
    --add-data "CHANGELOG.md;." ^
    --add-data "assets;assets" ^
    -n Facturation ^
    main.py

echo.
echo Termine : dist\Facturation.exe
pause
