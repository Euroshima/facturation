@echo off
REM ==================================================
REM Script de build pour l'app Facturation
REM - Nettoie les anciens fichiers
REM - Installe/Met à jour PyInstaller si besoin
REM - Génère l'exécutable .exe avec PyInstaller
REM ==================================================

echo [1/4] Nettoyage des anciens builds...
rmdir /s /q build dist 2>nul

echo [2/4] Vérification de PyInstaller...
py -m pip install --upgrade pip >nul
py -m pip install pyinstaller >nul

echo [3/4] Compilation avec PyInstaller...
REM --paths=src : ajoute le dossier src au PYTHONPATH
REM --name=Facturation : nom du .exe généré
REM --icon=assets\icon.ico : optionnel si tu mets une icône
py -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --paths=src ^
    --name=Facturation ^
    main.py

echo [4/4] Terminé !
echo Ton exécutable est disponible dans: dist\Facturation.exe

pause
