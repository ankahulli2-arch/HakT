@echo off
cd /d "%~dp0"
echo === Hal: запуск стенда ===

docker info >nul 2>&1 && goto up

echo Docker не отвечает - запускаю Docker Desktop...
if exist "C:\Program Files\Docker\Docker\Docker Desktop.exe" goto dd_std
if exist "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe" goto dd_user
echo НЕ НАШЁЛ Docker Desktop. Установи его и запусти start.cmd снова.
pause
exit /b 1

:dd_std
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
goto dd_wait

:dd_user
start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"

:dd_wait
echo Жду готовности Docker (обычно около минуты)...
:dd_loop
ping -n 6 127.0.0.1 >nul
docker info >nul 2>&1 || goto dd_loop

:up
echo Поднимаю контейнеры: postgres, redis, api, frontend...
docker compose up -d
if errorlevel 1 (echo Ошибка docker compose up & pause & exit /b 1)

echo Жду отклика сервисов...
echo (первый запуск фронта устанавливает зависимости - 2-5 минут, дальше быстро)

:waitapi
curl -s -m 3 http://localhost:8000/api/testing/specializations >nul 2>&1 || (ping -n 5 127.0.0.1 >nul & goto waitapi)
:waitweb
curl -s -m 3 -o nul http://localhost:3000 || (ping -n 10 127.0.0.1 >nul & goto waitweb)

echo.
echo   Готово!
echo   Стенд:    http://localhost:3000
echo   Swagger:  http://localhost:8000/api/docs
echo.
echo   Работодатель:  techlog@techlogistics.ru / Employer2026!
echo   Кандидат:      demo_cand_001@example.ru / Candidate2026!
echo.
start http://localhost:3000
pause
