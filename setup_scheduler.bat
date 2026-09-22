@echo off
:: LinkedIn Job Tracker — Task Scheduler Kurulum
:: Yönetici olarak çalıştır (sağ tık → Yönetici olarak çalıştır)

echo LinkedIn Job Tracker zamanlayici kuruluyor...

schtasks /create ^
  /tn "LinkedInJobTracker" ^
  /tr "\"%~dp0schedule_pipeline.bat\"" ^
  /sc DAILY ^
  /st 09:00 ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% equ 0 (
    echo.
    echo Basariyla kuruldu! Her sabah 09:00'da otomatik calisacak.
    echo Zamanlayici listesi:
    schtasks /query /tn "LinkedInJobTracker"
) else (
    echo.
    echo HATA: Zamanlayici kurulamadi. Yonetici olarak calistirdiginizdan emin olun.
)

pause
