# 🚀 PersAcc - Complete Setup Guide

This guide covers all installation methods for PersAcc, from quick local setup to Docker deployment with AI features.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Method 1: Local Installation (Recommended for Development)](#method-1-local-installation)
- [Method 2: Docker Deployment (Recommended for Production)](#method-2-docker-deployment)
- [AI Features Setup (Optional but Recommended)](#ai-features-setup)
- [Database Initialization](#database-initialization)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### For Local Installation
- **Python** 3.9 or higher
- **pip** (comes with Python)
- **Git** (to clone the repository)

### For Docker Installation
- **Docker** 20.10+ [(Install Docker)](https://docs.docker.com/get-docker/)
- **Docker Compose** (optional, for easier management)

### For AI Features (Optional)
- **Ollama** [(Install Ollama)](https://ollama.com/download)
- At least **4GB RAM** for light models, **8GB+** recommended for quality models

---

## Method 1: Local Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/Alvaro-San-Cav/PersAcc.git
cd PersAcc
```

### Step 2: Create Virtual Environment (Recommended)

**On Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Contents of requirements.txt:**
```
streamlit>=1.28.0
plotly>=5.18.0
pandas>=2.0.0
requests>=2.31.0
streamlit-quill>=0.1.0
scikit-learn>=1.3.0
numpy>=1.24.0
```

### Step 4: Initialize Database

The database will be created automatically on first run, but you can initialize it manually:

```bash
python scripts/setup_db.py
```

This creates:
- `data/finanzas.db` - SQLite database
- `data/config.json` - Default configuration

### Step 5: Run the Application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`

**First-time setup:**
1. Go to **Utilities > Configuration**
2. Set your currency and defaults
3. (Optional) Enable AI features
4. Start adding transactions!

---

## Method 2: Docker Deployment

### Quick Start with Docker

```bash
# Build image
docker build -t persacc:latest .

# Run container
docker run -p 8501:8501 \
  -v $(pwd)/data:/app/data \
  persacc:latest
```

Access at `http://localhost:8501`

### Using Docker Compose (Recommended)

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  persacc:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./locales:/app/locales
    environment:
      - STREAMLIT_SERVER_PORT=8501
      - STREAMLIT_SERVER_ADDRESS=0.0.0.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Run:**
```bash
docker-compose up -d
```

**Stop:**
```bash
docker-compose down
```

### Docker with Ollama (AI Features)

To enable AI features in Docker, Ollama must be accessible:

**Option A: Ollama on Host Machine**
```bash
# Run Ollama on host
ollama serve

# Run PersAcc container with host network
docker run --network="host" \
  -v $(pwd)/data:/app/data \
  persacc:latest
```

**Option B: Ollama in Docker Compose**
```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped

  persacc:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
    environment:
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - ollama
    restart: unless-stopped

volumes:
  ollama_data:
```

---

## AI Features Setup

PersAcc uses **Ollama** for local AI processing (completely offline, private, and free).

### Step 1: Install Ollama

1. **Download**: Visit [ollama.com/download](https://ollama.com/download)
2. **Install**: Run the installer for your OS
3. **Verify**:
   ```bash
   ollama --version
   ```

Ollama runs as a background service on port `11434`.

### Step 2: Download a Model

Choose based on your resources for my testing I used

```bash
ollama pull qwen3:8b    # great performance
ollama pull gemma2      # Google's model
```

### Step 3: Configure PersAcc

Edit `data/config.json`:

```json
{
  "llm": {
    "enabled": true,
    "model_tier": "qwen3:8b",
    "max_tokens": 300
  }
}
```

**Or** use the UI:
1. Go to **Utilities > AI Configuration**
2. Enable AI
3. Select model tier
4. Save

### Step 4: Test AI Features

**Search Assistant:**
1. Go to **Search Assistant** tab
2. Type: "¿Cuánto gasté en comida el mes pasado?"
3. Review extracted parameters
4. Execute search

**ML Projections:**
1. Go to **Projections** tab
2. Set year range
3. View AI-powered forecasts

**Historical Insights:**
1. Go to **Historical** tab
2. Select a year with data
3. Click **Generate AI Analysis**

---

## Database Initialization

### Automatic (Default)
Database is created automatically on first run.

### Manual Setup

```python
# scripts/setup_db.py
import sqlite3
from pathlib import Path

Path("data").mkdir(exist_ok=True)
conn = sqlite3.connect("data/finanzas.db")

# Run migrations
# (See scripts/setup_db.py for full SQL schema)

conn.close()
```

### Schema Overview

**Tables:**
- `movimientos` - All financial transactions
- `categorias` - Expense/income categories
- `cierres_mensuales` - Monthly closing snapshots
- `configuracion` - App configuration

---

## Configuration

### Config File Location
`data/config.json`

### Example Configuration

```json
{
  "currency": {
    "symbol": "€",
    "code": "EUR"
  },
  "month_close": {
    "balance_after_salary": false,
    "default_surplus_retention": 50,
    "default_salary_retention": 20
  },
  "defaults": {
    "category_id": 1,
    "concept": "Varios",
    "relevance": "LI"
  },
  "llm": {
    "enabled": true,
    "model_tier": "qwen3:8b",
    "max_tokens": 300
  }
}
```

### Configuration via UI

Most settings can be configured in **Utilities > Configuration**:
- Currency symbol
- Default values for quick add
- Month closing preferences
- AI model selection

---

## Troubleshooting

### Database Issues

**Problem**: "Database is locked"
```bash
# Stop all Streamlit instances
pkill -f streamlit

# Restart
streamlit run app.py
```

**Problem**: Corrupted database
```bash
# Backup first!
cp data/finanzas.db data/finanzas.db.backup

# Rebuild (careful, this deletes data!)
rm data/finanzas.db
python scripts/setup_db.py
```

### Ollama Issues

**Problem**: "Ollama not running"
```powershell
# Windows
ollama serve

# Check status
Get-Process ollama
```

```bash
# macOS/Linux
brew services start ollama  # If installed via Homebrew
# or
ollama serve
```

**Problem**: Model not found
```bash
# List downloaded models
ollama list

# Download missing model
ollama pull phi3
```

**Problem**: Slow AI responses
- Use a smaller model (`tinyllama`)
- Check RAM usage
- Restart Ollama

### Docker Issues

**Problem**: Port already in use
```bash
# Use different port
docker run -p 8502:8501 persacc:latest
```

**Problem**: Volume permission errors
```bash
# Fix permissions
chmod -R 755 ./data
```

**Problem**: Container won't start
```bash
# Check logs
docker logs <container-id>

# Remove and rebuild
docker rm <container-id>
docker build --no-cache -t persacc:latest .
```

### Streamlit Issues

**Problem**: "Module not found"
```bash
pip install -r requirements.txt --upgrade
```

**Problem**: Port already in use
```bash
streamlit run app.py --server.port=8502
```

**Problem**: App won't reload
```bash
# Clear Streamlit cache
rm -rf ~/.streamlit/cache/
```

---

## Advanced Configuration

### Environment Variables

```bash
# Set Streamlit options
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_HEADLESS=true

# Set Ollama host (if remote)
export OLLAMA_HOST=http://remote-host:11434
```

### Custom Database Location

Edit `src/database.py`:
```python
DB_PATH = Path("/custom/path/finanzas.db")
```

### Multiple Instances

Run multiple instances for different accounts:

```bash
# Instance 1 (Personal)
streamlit run app.py --server.port=8501

# Instance 2 (Business)
streamlit run app.py --server.port=8502 -- --data-dir=./data-business
```

---

## Next Steps

1. ✅ **Add your first transaction** - Use Quick Add in sidebar
2. ✅ **Configure categories** - Go to Utilities > Categories
3. ✅ **Import historical data** - Use CSV import if migrating
4. ✅ **Close your first month** - Follow the wizard in Month Closing
5. ✅ **Enable AI features** - Set up Ollama for smart insights
6. ✅ **Explore projections** - See your financial future with ML

---

**Version**: 2.0  
**Last updated**: January 2026
