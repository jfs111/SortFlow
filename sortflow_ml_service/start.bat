@echo off
REM start.bat - Démarrage du ML Service

echo ========================================
echo  SORTFLOW ML SERVICE
echo ========================================
echo.

REM Activer environnement conda
call conda activate sortflow
if errorlevel 1 (
    echo [ERREUR] Environment 'sortflow' introuvable
    echo Creez-le avec: conda create -n sortflow python=3.11 -y
    pause
    exit /b 1
)

echo [1/3] Environment active: sortflow
echo.

REM Vérifier les dépendances
echo [2/3] Verification des dependances...
python -c "import fastapi, torch, numpy" 2>nul
if errorlevel 1 (
    echo [ATTENTION] Dependencies manquantes
    echo Installation...
    pip install -r requirements.txt
)

echo [3/3] Demarrage du service...
echo.
echo ========================================
echo  Service disponible sur:
echo  - http://localhost:8000
echo  - Docs: http://localhost:8000/docs
echo ========================================
echo.

REM Démarrer FastAPI
python main.py

pause