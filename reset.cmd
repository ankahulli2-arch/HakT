@echo off
cd /d "%~dp0"
echo Полный сброс демо-данных (пересоздание базы + сид, ~40 секунд)...
curl -s -X POST "http://localhost:8000/api/admin/seed?reset=true"
echo.
echo Готово - стенд как на скриншотах презентации.
pause
