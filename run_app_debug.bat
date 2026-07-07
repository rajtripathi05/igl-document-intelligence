@echo off
REM Foreground launch with full output captured, to diagnose startup failures.
cd /d "%~dp0"
taskkill /F /FI "WINDOWTITLE eq IGL Document Intelligence (server)*" >nul 2>&1
echo Starting (foreground, logging to outputs\streamlit_log.txt) ...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --server.port 8501 --server.address 0.0.0.0 > "outputs\streamlit_log.txt" 2>&1
) else (
    python -m streamlit run app.py --server.headless true --server.port 8501 --server.address 0.0.0.0 > "outputs\streamlit_log.txt" 2>&1
)
