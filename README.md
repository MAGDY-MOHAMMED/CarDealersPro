# CarDealersPro - Professional Car Dealership Management System

## Overview 
CarDealersPro is a cutting-edge dealership management platform integrating:
- Inventory management
- Financial transactions
- Loan processing
- ML-powered car pricing & inspection
- User rating systems

## 🚀 Production Setup

### Docker Installation
```bash
docker compose up -d --build
```

### Configuration
Create `.env` file with:
```env
DATABASE_URL="postgresql://user:pass@neon-host/project"
ML_MODELS_DIR="/app/models"
```

## 🤖 AI Pipeline Architecture
```mermaid
graph LR
A[Car Image] --> B(Damage Detection)
C[Car Features] --> D(Price Prediction)
B --> E(Damage Report)
D --> F(Price Estimate)
```