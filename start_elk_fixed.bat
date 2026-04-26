@echo off
REM ELK Stack Startup Script for Windows (Fixed Version)
REM ====================================================

setlocal enabledelayedexpansion

echo ========================================
echo ELK Stack Startup Script for CarDealersPro
echo ========================================
echo.

REM Check if Docker is running
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not running or not installed!
    pause
    exit /b 1
)

echo [1/4] Checking Docker services...
docker-compose ps

echo.
echo [2/4] Starting Elasticsearch...
docker-compose up -d elasticsearch

REM Wait for Elasticsearch with timeout
set /a counter=0
:wait_elasticsearch
set /a counter+=1
if !counter! gtr 60 (
    echo ERROR: Elasticsearch startup timeout!
    pause
    exit /b 1
)

curl -s http://localhost:9200/_cluster/health >nul 2>&1
if errorlevel 1 (
    echo Waiting for Elasticsearch... (!counter!/60)
    timeout /t 5 /nobreak >nul
    goto wait_elasticsearch
)

echo Elasticsearch is ready!

echo.
echo [3/4] Starting Kibana...
docker-compose up -d kibana

REM Wait for Kibana with timeout
set /a counter=0
:wait_kibana
set /a counter+=1
if !counter! gtr 60 (
    echo ERROR: Kibana startup timeout!
    pause
    exit /b 1
)

curl -s http://localhost:5601/api/status >nul 2>&1
if errorlevel 1 (
    echo Waiting for Kibana... (!counter!/60)
    timeout /t 5 /nobreak >nul
    goto wait_kibana
)

echo Kibana is ready!

echo.
echo [4/4] Starting Filebeat...
docker-compose up -d filebeat

echo.
echo ========================================
echo ELK Stack is now running successfully!
echo ========================================
echo.
echo Services:
echo   Elasticsearch: http://localhost:9200
echo   Kibana:        http://localhost:5601
echo   Filebeat:      Collecting logs...
echo.

echo Container status:
docker-compose ps

echo.
echo To stop the stack: docker-compose down
echo To view logs:     docker-compose logs -f
echo.

pause
