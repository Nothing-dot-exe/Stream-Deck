@echo off
echo Starting Stream DeckX...
cd /d "%~dp0"

REM Activate the virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the unified app (GUI + Server)
start /b pythonw stream_deckx.py
exit
