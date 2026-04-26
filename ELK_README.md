# ELK Stack Integration for CarDealersPro


This project integrates the ELK Stack (Elasticsearch, Logstash, Kibana) with the CarDealersPro application to collect, store, and visualize PostgreSQL and application logs.

## Architecture

```
PostgreSQL → Filebeat → Elasticsearch → Kibana
     ↓              ↓           ↓
  JSON Logs    Log Collector   Data Store   Visualization
```

### 1. Elasticsearch
- **Port**: 9200
- **Purpose**: Store and index log data
- **Access**: http://localhost:9200

### 2. Kibana
- **Port**: 5601
- **Purpose**: Visualize and analyze logs
- **Access**: http://localhost:5601

### 3. Filebeat
- **Purpose**: Collect logs from PostgreSQL and application
- **Configuration**: `filebeat.yml` or `filebeat_env.yml`

## Quick Start

### Using Scripts
```bash
# Linux/Mac
./start_elk.sh

# Windows (Batch)
start_elk.bat

# Windows (PowerShell)
.\start_elk.ps1

# Windows (Fixed Version)
start_elk_fixed.bat
```

### Manual Start
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

## Configuration

### Filebeat Configuration Files

#### `filebeat.yml` (Main Configuration)
- Complex configuration with JavaScript processors
- Multiple input paths
- Advanced template settings

#### `filebeat_simple.yml` (Simple Configuration)
- Basic configuration for PostgreSQL logs
- Simple template settings
- Recommended for production

#### `filebeat_env.yml` (Environment Variables)
- Uses environment variables for configuration
- Most stable and recommended version

### Docker Compose Configuration

The `docker-compose.yml` file defines:
- **PostgreSQL**: Database service
- **Elasticsearch**: Data storage
- **Kibana**: Visualization
- **Filebeat**: Log collection

## Log Sources

### PostgreSQL Logs
- **Format**: JSON
- **Location**: `/var/log/postgresql/`
- **Fields**: timestamp, user, dbname, message, application_name

### Application Logs
- **Format**: JSON
- **Location**: `/var/log/cardealerspro/`
- **Fields**: @timestamp, message, request_id, project_name

## Data Flow

1. **PostgreSQL** generates JSON logs
2. **Filebeat** collects logs and sends to Elasticsearch
3. **Elasticsearch** indexes and stores the data
4. **Kibana** provides visualization interface

## Kibana Setup

### Create Data View
1. Open Kibana: http://localhost:5601
2. Go to **Stack Management** → **Data Views**
3. Click **Create data view**
4. **Name**: `cardealerspro-logs-*`
5. **Time field**: `@timestamp`
6. Click **Create data view**

### View Logs
1. Go to **Discover**
2. Select `cardealerspro-logs-*`
3. Apply filters as needed:
   - `log_type: postgresql`
   - `message: "Select * from cars"`
   - `user: postgres`

## Troubleshooting

### Common Issues

#### Filebeat Not Starting
```bash
# Check logs
docker logs filebeat

# Restart Filebeat
docker-compose restart filebeat

# Check configuration
docker exec filebeat cat /usr/share/filebeat/filebeat.yml
```

#### No Indices in Elasticsearch
```bash
# Check indices
curl http://localhost:9200/_cat/indices

# Check cluster health
curl http://localhost:9200/_cluster/health

# Restart services
docker-compose restart
```

#### Kibana Cannot Connect to Elasticsearch
```bash
# Check Elasticsearch
curl http://localhost:9200

# Check Kibana logs
docker logs kibana

# Restart Kibana
docker-compose restart kibana
```

### Debug Commands

```bash
# Check all services
docker-compose ps

# View logs for specific service
docker-compose logs -f filebeat
docker-compose logs -f elasticsearch
docker-compose logs -f kibana

# Test Elasticsearch connection
curl http://localhost:9200/_cluster/health

# Test Kibana connection
curl http://localhost:5601/api/status

# Check Filebeat configuration
docker exec filebeat filebeat test config
docker exec filebeat filebeat test output
```

## Performance Tuning

### Elasticsearch
- **Memory**: Adjust `ES_JAVA_OPTS` in docker-compose.yml
- **Storage**: Use persistent volumes for data
- **Index Lifecycle**: Configure ILM policies

### Filebeat
- **Batch Size**: Adjust `bulk_max_size`
- **Compression**: Enable gzip compression
- **Backpressure**: Configure queue settings

### Kibana
- **Caching**: Enable browser caching
- **Performance**: Optimize dashboard queries

## Security Considerations

### Production Environment
- Enable Elasticsearch security
- Use HTTPS/TLS encryption
- Implement authentication
- Configure firewall rules

### Network Security
- Use internal Docker network
- Restrict external access
- Monitor network traffic

## Maintenance

### Backup and Recovery
```bash
# Backup Elasticsearch data
docker exec elasticsearch curl -X PUT "localhost:9200/_snapshot/backup/snapshot_1"

# Restore from backup
docker exec elasticsearch curl -X POST "localhost:9200/_snapshot/backup/snapshot_1/_restore"
```

### Log Rotation
```bash
# Configure log rotation in Elasticsearch
curl -X PUT "localhost:9200/_index_template/cardealerspro" -H "Content-Type: application/json" -d '{
  "index_patterns": ["cardealerspro-logs-*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "cardealerspro-policy",
      "index.lifecycle.rollover_alias": "cardealerspro-logs"
    }
  }
}'
```

### Monitoring
- Monitor cluster health
- Track disk usage
- Monitor query performance
- Set up alerts

## Advanced Features

### Custom Dashboards
- Create visualizations in Kibana
- Build custom dashboards
- Set up automated reports

### Alerting
- Configure Watcher alerts
- Set up notification rules
- Integrate with external systems

### Machine Learning
- Enable ML features in Elasticsearch
- Create anomaly detection jobs
- Monitor system behavior

## Scripts Reference

### `start_elk.sh`
Linux/Mac script to start ELK stack with health checks

### `start_elk.bat`
Windows batch script for basic startup

### `start_elk.ps1`
PowerShell script with enhanced error handling

### `start_elk_fixed.bat`
Windows batch script with timeout and error handling

### `restart_filebeat.bat`
Script to restart Filebeat service only

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Docker logs
3. Verify configuration files
4. Test network connectivity

## License

This ELK integration is part of the CarDealersPro project.
