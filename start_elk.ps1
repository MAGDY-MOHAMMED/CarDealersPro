# ELK Stack Startup Script for PowerShell
# =======================================

Write-Host "Starting ELK Stack for CarDealersPro..." -ForegroundColor Green

# Start Elasticsearch
Write-Host "Starting Elasticsearch..." -ForegroundColor Yellow
docker-compose up -d elasticsearch

# Wait for Elasticsearch to be ready
Write-Host "Waiting for Elasticsearch to be ready..." -ForegroundColor Yellow
$elasticsearchReady = $false
while (-not $elasticsearchReady) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:9200/_cluster/health" -TimeoutSec 5
        if ($response.status -eq "green") {
            $elasticsearchReady = $true
            Write-Host "Elasticsearch is ready!" -ForegroundColor Green
        } else {
            Write-Host "Elasticsearch status: $($response.status). Waiting..." -ForegroundColor Yellow
            Start-Sleep 5
        }
    } catch {
        Write-Host "Elasticsearch is not ready yet. Waiting..." -ForegroundColor Yellow
        Start-Sleep 5
    }
}

# Start Kibana
Write-Host "Starting Kibana..." -ForegroundColor Yellow
docker-compose up -d kibana

# Wait for Kibana to be ready
Write-Host "Waiting for Kibana to be ready..." -ForegroundColor Yellow
$kibanaReady = $false
while (-not $kibanaReady) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:5601/api/status" -TimeoutSec 5
        if ($response.overall.state -eq "green") {
            $kibanaReady = $true
            Write-Host "Kibana is ready!" -ForegroundColor Green
        } else {
            Write-Host "Kibana status: $($response.overall.state). Waiting..." -ForegroundColor Yellow
            Start-Sleep 5
        }
    } catch {
        Write-Host "Kibana is not ready yet. Waiting..." -ForegroundColor Yellow
        Start-Sleep 5
    }
}

# Start Filebeat
Write-Host "Starting Filebeat..." -ForegroundColor Yellow
docker-compose up -d filebeat

Write-Host "ELK Stack is now running!" -ForegroundColor Green
Write-Host "Elasticsearch: http://localhost:9200"
Write-Host "Kibana: http://localhost:5601"
Write-Host "Filebeat: Collecting logs..."

# Show running containers
Write-Host "Running containers:" -ForegroundColor Cyan
docker-compose ps

Write-Host "Press Enter to exit..." -ForegroundColor Cyan
Read-Host
