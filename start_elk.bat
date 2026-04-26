@echo off
REM ELK Stack Startup Script for Windows
REM =====================================

echo Starting ELK Stack for CarDealersPro...

REM Start Elasticsearch
echo Starting Elasticsearch...
docker-compose up -d elasticsearch

REM Wait for Elasticsearch to be ready
echo Waiting for Elasticsearch to be ready...
:wait_elasticsearch
curl -s http://localhost:9200/_cluster/health | findstr "green" >nul
if errorlevel 1 (
    echo Elasticsearch is not ready yet. Waiting...
    timeout /t 5 /nobreak >nul
    goto wait_elasticsearch
)

echo Elasticsearch is ready!

REM Start Kibana
echo Starting Kibana...
docker-compose up -d kibana

REM Wait for Kibana to be ready
echo Waiting for Kibana to be ready...
:wait_kibana
curl -s http://localhost:5601/api/status | findstr "green" >nul
if errorlevel 1 (
    echo Kibana is not ready yet. Waiting...
    timeout /t 5 /nobreak >nul
    goto wait_kibana
)

echo Kibana is ready!

REM Start Filebeat
echo Starting Filebeat...
docker-compose up -d filebeat

echo ELK Stack is now running!
echo Elasticsearch: http://localhost:9200
echo Kibana: http://localhost:5601
echo Filebeat: Collecting logs...

REM Show running containers
echo Running containers:
docker-compose ps

pause
