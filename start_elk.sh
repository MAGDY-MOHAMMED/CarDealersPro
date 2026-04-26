#!/bin/bash

# ELK Stack Startup Script
# ========================

echo "Starting ELK Stack for CarDealersPro..."

# Start Elasticsearch
echo "Starting Elasticsearch..."
docker-compose up -d elasticsearch

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch to be ready..."
until curl -s http://localhost:9200/_cluster/health | grep -q '"status":"green"'; do
    echo "Elasticsearch is not ready yet. Waiting..."
    sleep 5
done

echo "Elasticsearch is ready!"

# Start Kibana
echo "Starting Kibana..."
docker-compose up -d kibana

# Wait for Kibana to be ready
echo "Waiting for Kibana to be ready..."
until curl -s http://localhost:5601/api/status | grep -q '"overall":{"state":"green"'; do
    echo "Kibana is not ready yet. Waiting..."
    sleep 5
done

echo "Kibana is ready!"

# Start Filebeat
echo "Starting Filebeat..."
docker-compose up -d filebeat

echo "ELK Stack is now running!"
echo "Elasticsearch: http://localhost:9200"
echo "Kibana: http://localhost:5601"
echo "Filebeat: Collecting logs..."

# Show running containers
echo "Running containers:"
docker-compose ps
