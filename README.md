# 💰 PersAcc - Personal Accounting System

> Personal accounting system with monthly closing methodology, automatic savings retention, and spending quality analysis.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![SQLite](https://img.shields.io/badge/SQLite-3-green.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE)

## 🎯 What is PersAcc?

**PersAcc** is a personal accounting application designed for people who want **full control over their monthly finances** through a rigorous accounting closing system.

### Key Features

✅ **Automatic Month Closing** - Step-by-step wizard that calculates retentions, generates immutable snapshots, and opens the next month  
✅ **Configurable Retentions** - Set savings/investment % on surplus balance and salary  
✅ **Expense Classification** - Relevance system (Necessary, Like, Superfluous, Nonsense) to analyze behavior  
✅ **Editable Table** - Modify transactions inline with closed month validation  
✅ **Historical Dashboard** - Annual KPIs, monthly evolution, and trend analysis  
✅ **CSV Import/Export** - Migrate from other apps or create backups  
✅ **Modular Architecture** - Clean and maintainable code (8 UI modules + constants + business logic)

## 🚀 Quick Start

### Requirements

- Python 3.8 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/PersAcc.git
cd PersAcc

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python setup_db.py
```

### Run the Application

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## 📸 Screenshots

### Main Dashboard
Monthly analysis view with real-time KPIs, editable transactions table, and spending quality chart.

### Month Closing Wizard
Guided 4-step process: real balance, new salary, retentions, and confirmation.

### Annual Historical Analysis
Dashboard with monthly evolution, aggregated KPIs, and curious metrics.

## 📖 Key Concepts

### Month Closing

The **monthly closing flow** is the heart of PersAcc. Follow these steps:

#### When to Close the Month?
Once you receive next month's salary (even if it's on the 28th), you should start closing the current month.

#### Wizard Steps

1. **Go to the "Month Closing" tab** - The system automatically detects the next month to close

2. **Enter your bank balance** - Input the exact value shown in your bank account at that moment
   - *Traditional mode*: Balance **before** receiving salary
   - *Alternative mode*: Balance **after** receiving salary (configurable in settings)

3. **Enter the salary amount** - Input the gross salary you just received

4. **Configure retentions** - Set what percentage to allocate to investment/savings:
   - **% Surplus Retention**: From leftover money before the new salary
   - **% Salary Retention**: From the new salary received

5. **Execute the closing** - The system:
   - Creates automatic investment entries
   - Generates the salary as income in the new month
   - Calculates and displays the final result
   - Automatically switches to the next month

**Result**: Closed and immutable month + next month ready with correct opening balance.

### Spending Relevance

Classify each expense as:
- **NE** (Necessary) - Essential for living
- **LI** (Like) - Brings happiness/well-being  
- **SUP** (Superfluous) - Occasionally justifiable
- **TON** (Nonsense) - Impulsive or regretted

**Goal**: Analyze what % of your spending goes to each category and improve habits.

### Tech Stack

- **Frontend**: Streamlit 
- **Backend**: Python 3.8+ 
- **Database**: SQLite 

## 📝 Typical Usage

### Daily Workflow

1. **Quick Add** (sidebar) - Log expenses in 10 seconds
2. **Analysis** - Review transactions table and monthly KPIs
3. **End of month** - Closing wizard (5 minutes)

### Closing Example

```
Month: January 2026
Real balance: €1,245
New salary: €2,500
Surplus retention: 50% → €622.50
Salary retention: 20% → €500

→ February starts with €622.50 + €2,500 - €500 = €2,622.50 operational
```

### Contributing

1. Fork the project
2. Create a branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push: `git push origin feature/amazing-feature`
5. Open a Pull Request

[![License](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](LICENSE)

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)** license.

The LICENSE file contains the full text of the license.  
**Summary**: You are free to share and adapt the material for non-commercial purposes, as long as you give appropriate credit and distribute your contributions under the same license.


## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io/) - Amazing and easy-to-use UI framework

## 📞 Contact

**Author**: Alvaro Sánchez  
**GitHub**: [@Alvaro-San-Cav](https://github.com/Alvaro-San-Cav)

---

⭐ If PersAcc is useful to you, give the repo a star!

**Version**: 1.2  
**Last updated**: January 2026
