@echo off
REM Restart Filebeat Script
REM =====================

echo Restarting Filebeat...

REM Stop Filebeat
echo Stopping Filebeat...
docker-compose stop filebeat

REM Wait a moment
timeout /t 3 /nobreak >nul

REM Start Filebeat
echo Starting Filebeat...
docker-compose start filebeat

REM Wait a moment
timeout /t 5 /nobreak >nul

REM Check status
echo Checking Filebeat status...
docker-compose ps filebeat

REM Show logs
echo.
echo Filebeat logs:
docker logs filebeat --tail 10

echo.
echo Filebeat restarted successfully!
pause
