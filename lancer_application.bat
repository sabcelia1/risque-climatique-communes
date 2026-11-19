@echo off
REM Ouvre l application Streamlit dans le navigateur (lancer d abord lancer.bat une fois).
cd /d "%~dp0"
echo Application en cours de demarrage : http://localhost:8501  (fermer cette fenetre pour l arreter)
start "" cmd /c "timeout /t 6 >nul & start http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run app\streamlit_app.py --server.port 8501
