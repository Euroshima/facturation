@echo off
REM ==================================================
REM Script de build pour l'app Facturation
REM - Nettoie les anciens fichiers
REM - Installe/Met a jour PyInstaller si besoin
REM - Genere UN SEUL .exe avec PyInstaller
REM
REM NOTE : version_info.txt (ressource de version Windows) doit etre mis a jour
REM EN MEME TEMPS que src\core\version.py (__version__). En CI, ce fichier est
REM regenere automatiquement depuis le tag git.
REM ==================================================

echo [1/4] Nettoyage des anciens builds...
rmdir /s /q build dist 2>nul

echo [2/4] Verification des dependances...
py -m pip install --upgrade pip >nul
py -m pip install -r requirements.txt >nul
py -m pip install pyinstaller >nul

echo [3/4] Compilation avec PyInstaller...
REM --onefile         : un seul fichier .exe
REM --noupx           : pas de compression UPX (marqueur classique de malware pour les AV)
REM --version-file    : ressource de version Windows (editeur, description, version)
REM --paths=src       : ajoute le dossier src au PYTHONPATH
REM --collect-all psycopg2 : embarque le driver Postgres COMPLET (module + _psycopg + DLL libpq)
REM --hidden-import   : securite supplementaire pour l'extension binaire
REM -n Facturation    : nom de l'exe genere
py -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --noupx ^
    --clean ^
    --paths=src ^
    --collect-all psycopg2 ^
    --hidden-import psycopg2 ^
    --hidden-import psycopg2._psycopg ^
    --hidden-import psycopg2.extras ^
    --add-data "CHANGELOG.md;." ^
    --add-data "assets;assets" ^
    --icon "assets/hytris.ico" ^
    --version-file version_info.txt ^
    -n Facturation ^
    main.py

echo [4/4] Termine !
echo Ton executable : dist\Facturation.exe

pause
