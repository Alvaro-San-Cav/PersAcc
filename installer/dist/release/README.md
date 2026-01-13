# 💰 PersAcc - Windows Installer

**Version 3.0** | Personal Accounting System  
© 2026 Alvaro Sanchez Cava

---

## 📦 What You've Downloaded

This package contains:
- `PersAcc_Installer.exe` - Installation wizard
- `TRUSTED_SOFTWARE_WARNING.txt` - Important security information
- `README.md` - This file

---

## 🚀 Quick Start

### Step 1: Run the Installer

1. **Double-click** `PersAcc_Installer.exe`
2. **Windows SmartScreen Warning**: If you see a blue screen saying "Windows protected your PC":
   - Click **"More info"** (Más información)
   - Click **"Run anyway"** (Ejecutar de todas formas)
   - This is normal for independent software without costly certificates (~$400/year)

### Step 2: Follow the Installation Wizard

The installer will guide you through:
1. Language selection (Español/English)
2. License agreement (CC BY-NC-SA 4.0)
3. Prerequisites check (Python, Internet)
4. Installation location (default: `C:\Users\<YourUser>\AppData\Local\PersAcc`)
5. AI features configuration (optional)
6. Installation progress

### Step 3: Launch PersAcc

After installation:
- Use the **desktop shortcut**, or
- Find **PersAcc** in the **Start Menu**
- The app will open in your browser at `http://localhost:8501`

---

## 🤖 AI Features (Optional)

PersAcc includes AI-powered features for smart search and financial analysis.

**To enable AI:**
1. Download Ollama from: https://ollama.com/download
2. Install Ollama (simple wizard)
3. Open PowerShell and run:
   ```powershell
   ollama pull phi3
   ```
4. Enable AI in **Utilities > Configuration** within PersAcc

**Recommended models:**
- `phi3` - Balanced (2.3GB)
- `tinyllama` - Fast (0.6GB)
- `mistral` - Quality (4.1GB)

---

## ⚙️ What's Installed

- **Application files**: All PersAcc source code and assets
- **Python environment**: Self-contained virtual environment with all dependencies
- **Database**: SQLite database in `data/finanzas.db` (created on first run)
- **Desktop shortcut**: Quick access to launch PersAcc
- **Uninstaller**: Remove PersAcc from Control Panel

---

## ✨ Key Features

### Core Accounting
- **Automatic Month Closing** - Rigorous accounting with step-by-step wizard
- **Configurable Retentions** - Auto-savings on surplus/salary
- **Expense Classification** - Relevance system (Necessary, Like, Superfluous, Nonsense)
- **Consequences Account** - Track hidden costs and forced savings

### AI-Powered (with Ollama)
- **Chat Assistant** - Ask questions in natural language
- **AI Commentary** - Witty insights on your spending
- **Smart Search** - Natural language queries
- **Deep Analysis** - Personalized recommendations

### Analytics & Projections
- **Historical Dashboard** - Annual KPIs and trends
- **ML Projections** - 5+ year forecasts
- **Interactive Charts** - Plotly visualizations

### User Experience
- **Multi-language** - Spanish and English
- **Multi-currency** - EUR, USD, GBP, CHF, JPY, CNY, MXN, ARS, COP, BRL
- **Fast startup** - Lazy loading for sections
- **Built-in manual** - Complete user guide

---

## 🔧 Troubleshooting

### App won't start
- Right-click the desktop shortcut → **Run as Administrator**
- Check that Python is installed: Open PowerShell and run `py --version`

### "Port already in use" error
- Close any other instances of PersAcc
- Open PowerShell and run:
  ```powershell
  Get-Process | Where-Object {$_.ProcessName -like "*streamlit*"} | Stop-Process
  ```

### AI features not working
- Verify Ollama is running: Open PowerShell and run `ollama --version`
- Start Ollama: Run `ollama serve` in PowerShell
- Check model is downloaded: Run `ollama list`

### Need help?
- Visit: https://github.com/Alvaro-San-Cav/PersAcc
- Check the **Manual** tab inside PersAcc (complete user guide)

---

## 🛡️ Security Warning

> [!CAUTION]
> **ONLY download from the official GitHub repository**:
> https://github.com/Alvaro-San-Cav/PersAcc
>
> **Never install if obtained from third parties** - the file may have been tampered with.

---

## 📄 License

This software is licensed under **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International).

**Summary**: Free to use and modify for **non-commercial purposes** with attribution.

Full license: https://creativecommons.org/licenses/by-nc-sa/4.0/

---

## 🌐 Learn More

- **Full Documentation**: https://github.com/Alvaro-San-Cav/PersAcc
- **Setup Guide**: See `SETUP.md` in the repository
- **Ollama Setup**: See `OLLAMA_SETUP.md` in the repository

---

## 🙏 Acknowledgments

- [Streamlit](https://streamlit.io/) - UI framework
- [Ollama](https://ollama.com/) - Local AI inference
- [Plotly](https://plotly.com/) - Interactive visualizations
- [scikit-learn](https://scikit-learn.org/) - Machine learning

---

**Enjoy managing your personal finances with AI! 💰🤖**

*If PersAcc is useful to you, star the repo on GitHub ⭐*
