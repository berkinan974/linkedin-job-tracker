@echo off
:: LinkedIn Job Tracker — Günlük Pipeline
:: Bu .bat dosyasini Windows Task Scheduler ile çalıştır.
:: Öneri: Her sabah 09:00'da otomatik çalıştır.

cd /d "%~dp0"

:: Sanal ortamı etkinleştir
call venv\Scripts\activate.bat

:: Pipeline'ı çalıştır (scraper tarayıcı açacak, oturum Opera profilinden gelir)
py run_pipeline.py --skip-fetch

:: Hata varsa log bırak
if %ERRORLEVEL% neq 0 (
    echo [HATA] Pipeline basarisiz. Kod: %ERRORLEVEL% >> data\logs\scheduler_errors.log
)

deactivate
