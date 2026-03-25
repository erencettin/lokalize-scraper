@echo off
set "PYTHON_EXE=C:\Lokalize\LokalizeApp\temp_scraper_repo\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment not found at %PYTHON_EXE%
    pause
    exit /b 1
)
cd /d "C:\Lokalize\LokalizeApp\temp_scraper_repo"
"%PYTHON_EXE%" main.py --provider Passo
pause
