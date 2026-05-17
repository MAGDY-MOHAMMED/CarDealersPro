# AI Features Setup Guide

## Overview
The Car Dealers Pro project supports optional AI features for car analysis, recommendations, and inspection. AI dependencies are separated to keep the base build fast.

## Files Created
- `requirements-ai.txt` - Contains all AI/ML dependencies
- `Dockerfile` - Updated to conditionally install AI dependencies
- `docker-compose.yml` - Updated to pass ENABLE_AI build argument

## How to Enable AI Features

### Local Development
```bash
# Enable AI features
export ENABLE_AI=true
docker-compose build
docker-compose up
```

### Hugging Face Deployment
Add this to your Hugging Face Space settings or Dockerfile build args:
```yaml
build:
  args:
    - ENABLE_AI=true
```

Or in your Space settings:
- Go to Settings → Variables and Secrets
- Add variable: `ENABLE_AI` with value `true`

### Docker Build Directly
```bash
docker build --build-arg ENABLE_AI=true -t cardealers-api .
docker run -p 8000:8000 cardealers-api
```

## AI Dependencies Included
- **LLM Integration:** litellm, openai, huggingface_hub
- **Data Processing:** pandas, numpy, scipy
- **Tokenization:** tiktoken, tokenizers
- **Utilities:** joblib

## Default Behavior
- **ENABLE_AI=false** (default): Fast build (~10-15 minutes), no AI features
- **ENABLE_AI=true**: Slower build (~20-30 minutes), AI features enabled

## Environment Variables
Add these to your `.env` file when AI is enabled:
```env
ENABLE_AI=true
OPENAI_API_KEY=your_openai_key
# Or other LLM provider keys
```

## What AI Features Will Be Available
- Car analysis using LLMs
- Intelligent recommendations for clients
- AI-powered inspection reports
- Natural language queries for car data
