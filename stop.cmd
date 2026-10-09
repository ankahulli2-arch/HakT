@echo off
cd /d "%~dp0"
docker compose stop
echo.
echo Остановлено. Обратный запуск - start.cmd (быстро, всё закэшировано).
pause
