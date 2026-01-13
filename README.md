# 💰 PersAcc - Personal Accounting System

> Personal accounting system with monthly closing methodology, automatic savings retention, AI-powered financial analysis, and ML-based projections.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3-green.svg)](https://www.sqlite.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20AI-purple.svg)](https://ollama.com/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE)

## 🎯 What is PersAcc?

**PersAcc** is a personal accounting application designed for people who want **full control over their monthly finances** through a rigorous accounting closing system, enhanced with AI-powered insights and machine learning projections.

### ✨ Key Features

#### 📊 Core Accounting
- **Automatic Month Closing** - Step-by-step wizard that calculates retentions, generates immutable snapshots, and opens the next month
- **Configurable Retentions** - Set savings/investment % on surplus balance and salary
- **Expense Classification** - Relevance system (Necessary, Like, Superfluous, Nonsense) to analyze behavior
- **Consequences Account** - Automatic rules to track hidden costs and forced savings
- **Editable Table** - Modify transactions inline with closed month validation
- **Smart Category Sorting** - Categories auto-sort by historical usage patterns
- **Default Values** - Auto-fill concepts, amounts, and relevance per category
- **CSV Import/Export** - Migrate from other apps or create backups

#### 🤖 AI-Powered Features (Ollama)
- **Intelligent Chat Assistant** - Ask questions in natural language about your finances
- **Ledger AI Commentary** - Witty AI-generated comments on your monthly spending
- **Period Analysis** - Deep AI analysis of months or years with personalized recommendations
- **Smart Search** - Natural language queries with automatic parameter extraction

#### 📈 Analytics & Projections
- **Historical Dashboard** - Annual KPIs, monthly evolution, and trend analysis
- **ML Projections** - Predict salaries, expenses, and investments for 5+ years
- **Spending Quality Analysis** - Visual NE/LI/SUP/TON breakdown
- **Period Annotations** - Personal notes per month or year
- **Interactive Charts** - Plotly-powered visualizations with historical vs projected data

#### 🌍 User Experience
- **Multi-language** - Spanish and English
- **Multi-currency** - EUR, USD, GBP, CHF, JPY, CNY, MXN, ARS, COP, BRL
- **Lazy Loading** - Fast startup with on-demand section loading
- **Built-in Manual** - Complete user guide in both languages

## 🚀 Quick Start

See [**SETUP.md**](SETUP.md) for detailed installation instructions including:
- Local installation (Python)
- Docker deployment
- Ollama AI setup

### Minimal Setup (5 minutes)

```bash
# Clone repository
git clone https://github.com/Alvaro-San-Cav/PersAcc.git
cd PersAcc

# Install dependencies
pip install -r requirements.txt

# Run
streamlit run app.py
```

The app will open at `http://localhost:8501`

## 🧠 AI Features Setup

PersAcc uses **Ollama** for local AI processing (completely offline and free).

### Quick Ollama Setup

1. **Install Ollama**: Download from [ollama.com](https://ollama.com/download)
2. **Download a model**:
   ```bash
   ollama pull phi3  # Recommended (2.3GB, balanced)
   # Or: ollama pull tinyllama (0.6GB, fast)
   # Or: ollama pull mistral (4.1GB, quality)
   ```
3. **Enable in app**: Go to Utilities > Configuration > Enable AI Analysis
4. **Select model**: Choose from available models in AI Configuration section
5. **Start using**: Chat Assistant tab for queries, Ledger for AI comments

See [**OLLAMA_SETUP.md**](OLLAMA_SETUP.md) for detailed AI configuration.

## 📸 Screenshots

### Main Dashboard
Monthly analysis view with real-time KPIs, editable transactions table, and spending quality chart.

![Main Dashboard](assets/mainmenu_jan2026.png)

### Month Closing Wizard
Guided 4-step process: real balance, new salary, retentions, and confirmation.

![Month Closing Wizard](assets/monthclose_jan2026.png)

## 📖 Key Concepts

### 🤖 AI Chat Assistant

Ask questions in natural language about your finances:

**Examples:**
- "¿Cuánto gasté en transporte el año pasado?"
- "What are my biggest expenses this month?"
- "Busca gastos de Uber"
- "Show my savings rate for 2024"

**How it works:**
1. Enter your question in natural language (Spanish or English)
2. AI analyzes and extracts search parameters
3. Review results with AI-formatted responses
4. Follow up with related questions

### 📈 ML Projections

The **Projections** feature uses machine learning to forecast your financial future:

- **Income Projections** - Linear regression on historical salary data
- **Investment Forecasts** - Based on savings rate and automatic retentions
- **Expense Predictions** - Trend analysis with seasonality detection

Each projection includes confidence levels, trend indicators, and interactive charts.

### 💰 Month Closing

The **monthly closing flow** is the heart of PersAcc:

1. **Navigate to Month Closing** - System detects next month to close
2. **Enter bank balance** - Exact value from your bank account
3. **Enter salary amount** - New salary received
4. **Configure retentions** - Set surplus and salary retention %
5. **Review consequences** - If enabled, see rule-based forced savings
6. **Execute closing** - Creates entries and opens next month

**Result**: Immutable closed month + next month ready with correct opening balance.

### 🎯 Spending Relevance

Classify each expense as:
- **NE** (Necessary) - Essential for living
- **LI** (Like) - Brings happiness/well-being  
- **SUP** (Superfluous) - Occasionally justifiable
- **TON** (Nonsense) - Impulsive or regretted

**Goal**: Analyze spending patterns and improve financial habits.

### 📝 Annotations

Add personal notes to any month or year to remember context, decisions, or reflections. Notes are shown in read-only mode when reviewing closed periods.

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| Backend | Python 3.9+ |
| Database | SQLite |
| AI/LLM | Ollama (local) |
| ML | scikit-learn, NumPy |
| Charts | Plotly |
| Container | Docker (optional) |

## 📝 Configuration Options

All settings in **Utilities > Configuration**:

| Category | Options |
|----------|---------|
| **Language** | Spanish, English |
| **Currency** | EUR, USD, GBP, CHF, JPY, CNY, MXN, ARS, COP, BRL |
| **Toggles** | Relevance Analysis, Automatic Retentions, Consequences, AI Analysis |
| **Retentions** | Default % for surplus and salary |
| **Defaults** | Concepts, amounts, and relevance per category |
| **Closing Method** | Before salary / After salary |
| **AI Model** | Any Ollama model (phi3, tinyllama, mistral, llama3, qwen, etc.) |

## 🐳 Docker Deployment

```bash
# Build image
docker build -t persacc:latest .

# Run container
docker run -p 8501:8501 -v $(pwd)/data:/app/data persacc:latest
```

Data persists in the `./data` volume. See [SETUP.md](SETUP.md) for more details.

## 🌍 Internationalization

PersAcc supports multiple languages:
- 🇪🇸 Spanish (default)
- 🇬🇧 English

Change language in **Utilities > Configuration**.

## 🤝 Contributing

1. Fork the project
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license.

**Summary**: Free to share and adapt for non-commercial purposes with attribution.

## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io/) - Amazing UI framework
- [Ollama](https://ollama.com/) - Local AI inference
- [Plotly](https://plotly.com/) - Interactive visualizations
- [scikit-learn](https://scikit-learn.org/) - Machine learning library

## 📬 Contact

**Author**: Alvaro Sánchez  
**GitHub**: [@Alvaro-San-Cav](https://github.com/Alvaro-San-Cav)

---

⭐ If PersAcc is useful to you, give the repo a star!

**Version**: 3.0  
**Last updated**: January 2026
