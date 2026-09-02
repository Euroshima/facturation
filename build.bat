@echo off
REM ==================================================
REM Script de build pour l'app Facturation
REM - Nettoie les anciens fichiers
REM - Installe/Met a jour PyInstaller si besoin
REM - Genere l'application avec PyInstaller (mode dossier)
REM
REM NOTE IMPORTANTE : version_info.txt (ressource de version Windows) doit
REM etre mis a jour EN MEME TEMPS que src\core\version.py (__version__).
REM En CI, ce fichier est regenere automatiquement depuis le tag git.
REM ==================================================

echo [1/4] Nettoyage des anciens builds...
rmdir /s /q build dist 2>nul

echo [2/4] Verification des dependances...
py -m pip install --upgrade pip >nul
py -m pip install -r requirements.txt >nul
py -m pip install pyinstaller >nul

echo [3/4] Compilation avec PyInstaller...
REM --onedir          : distribution en dossier (bien moins de faux positifs antivirus que --onefile)
REM --noupx           : pas de compression UPX (UPX est un marqueur classique de malware pour les AV)
REM --version-file    : ressource de version Windows (editeur, description, version)
REM --paths=src       : ajoute le dossier src au PYTHONPATH
REM --collect-all psycopg2 : embarque le driver Postgres COMPLET (module + _psycopg + DLL libpq)
REM --hidden-import   : securite supplementaire pour l'extension binaire
REM -n Facturation    : nom de l'application generee
py -m PyInstaller ^
    --onedir ^
    --noconsole ^
    --noupx ^
    --clean ^
    --noconfirm ^
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
echo L'application se trouve dans: dist\Facturation\Facturation.exe
echo (Distribuez le DOSSIER dist\Facturation en entier, pas seulement l'exe.)

pause
