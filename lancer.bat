@echo off
REM Lance tout le pipeline : environnement Python, tests, ingestion, nettoyage, dbt, BigQuery.
REM Double-cliquez sur ce fichier, ou tapez "lancer" dans une console ouverte dans ce dossier.
cd /d "%~dp0"
"%SystemRoot%\System32\chcp.com" 65001 >nul 2>&1

if not exist ".venv\Scripts\python.exe" (
    echo === Creation de l'environnement Python...
    python -m venv .venv || goto :erreur
)

echo === Installation des librairies...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || goto :erreur

echo.
echo === Etape 0 : tests automatiques
".venv\Scripts\python.exe" -m pytest -q || goto :erreur

echo.
echo === Etape 1 : telechargement des donnees
".venv\Scripts\python.exe" src\ingest.py || goto :erreur

echo.
echo === Etape 2 : nettoyage et controles qualite
".venv\Scripts\python.exe" src\clean.py || goto :erreur

echo.
echo === Etape 3 : exploration
".venv\Scripts\python.exe" src\explorer.py || goto :erreur

echo.
echo === Etape 4 : modeles dbt et tests, en local (DuckDB)
".venv\Scripts\python.exe" src\lancer_dbt.py local || goto :erreur

echo.
echo === Etape 5 : modele de prediction (LightGBM, SHAP)
".venv\Scripts\python.exe" src\modele.py || goto :erreur

".venv\Scripts\python.exe" src\gcp.py
if errorlevel 1 (
    echo.
    echo === BigQuery ignore en local : il tourne sur GitHub Actions ^(voir docs\guide_gcp.md^)
    goto :fin
)

echo.
echo === Etape 6 : chargement dans BigQuery
".venv\Scripts\python.exe" src\load_bigquery.py || goto :erreur

echo.
echo === Etape 7 : modeles dbt et tests dans BigQuery
".venv\Scripts\python.exe" src\lancer_dbt.py bigquery || goto :erreur

:fin
echo.
echo === Termine ! Rapports : reports\qualite_donnees.md, reports\exploration.md et reports\modele.md
pause
exit /b 0

:erreur
echo.
echo *** Une erreur s'est produite : copiez tout le texte ci-dessus et envoyez-le a Claude.
pause
exit /b 1
