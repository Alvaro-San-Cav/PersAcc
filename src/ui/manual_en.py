"""
Manual Page - PersAcc (English)
Renders the complete application user manual.
"""
import streamlit as st


def render_manual_en():
    """Renders the complete application user manual in English."""
    st.markdown('<div class="main-header"><h1>📖 User Manual - PersAcc</h1></div>', unsafe_allow_html=True)
    
    # ============================================================================
    # INTRODUCTION
    # ============================================================================
    st.markdown("""
    ## 🎯 What is PersAcc?
    
    **PersAcc** is a personal accounting system with monthly closing, automatic retentions, and expense quality analysis.
    
    ### Key Features
    
    -  **Automatic Month Closing** - Wizard that calculates retentions and opens the next month
    -  **Configurable Retentions** - Define savings % on surplus and salary
    -  **Expense Classification** - NE/LI/SUP/TON system to analyze habits
    -  **Smart Sorting** - Categories auto-sort by historical usage
    -  **Auto Concepts** - Auto-fills concepts based on category
    -  **Consequences Account** - Automatic rules for hidden costs
    -  **Editable Table** - Modify transactions with closed month validation
    -  **Historical Dashboard** - Annual KPIs and monthly evolution
    -  **🤖 AI with Ollama** - Smart comments and deep analysis
    -  **📈 ML Projections** - Expense and investments/savings predictions
    -  **💬 Chat Assistant** - Ask about your finances in natural language
    -  **📝 Annotations** - Personal notes per period
    -  **Multi-language** - Spanish and English
    -  **Multi-currency** - Configure your currency (€, $, £, etc.)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # ADDING TRANSACTIONS
    # ============================================================================
    st.markdown("""
    ## ➕ Adding Transactions
    
    ### Quick Add (Sidebar)
    
    The quick form in the sidebar allows you to record expenses in seconds:
    
    1. **Date** - Select the transaction day
       > 💡 **Tip**: If you select a different month in the main navigation, the default date will be day 1 of that month.
    
    2. **Type** - Choose from:
       - **Expense** - Any money outflow
       - **Income** - Money inflows (salary, gifts, etc.)
       - **Investments/Savings** - Savings or investments
       - **Transfer In/Out** - Movements between accounts
    
    3. **Category** - Choose the appropriate category
       > 🌟 **NEW**: Categories are intelligently sorted based on your history:
       > - **First**: Most used categories in this month in previous years
       > - **Second**: Most used categories this year
       > - **Third**: Alphabetical order
    
    4. **Concept** - Describe the transaction
       > 🌟 **NEW**: The concept auto-fills if you've configured a default value for that category.
       > Configure it at: **Utilities → Configuration → Default Concepts**
    
    5. **Relevance** (expenses only) - Classify the expense quality
    
    6. **Amount** - Enter the quantity
    
    7. **Save** - Click the button to register
    
    ### Editable Table (Ledger)
    
    In the "Ledger" tab you can edit existing transactions:
    
    - ✏️ **Inline editing**: Click any cell to modify category, concept, amount, or relevance
    - 🗑️ **Bulk deletion**: Select multiple rows and delete them at once
    - 🔒 **Protection**: Closed months are locked against editing
    
    > ⚠️ **Important**: You cannot edit or delete entries from closed months.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # EXPENSE RELEVANCE
    # ============================================================================
    st.markdown("""
    ## 🎯 Expense Relevance
    
    Classify each expense to analyze your consumption behavior:
    
    | Code | Meaning | Examples |
    |------|---------|----------|
    | **NE** | Necessary | Food, rent, bills, transportation |
    | **LI** | I Like | Dinners with friends, gym, hobbies, leisure |
    | **SUP** | Superfluous | Extra clothes, decoration, whims |
    | **TON** | Nonsense | Impulse purchases, unused subscriptions |
    
    ### Goal
    
    Analyze what % of your expenses goes to each category. **Ideal distribution**:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    
    > 💡 **Tip**: You can disable relevance analysis in **Configuration** if you don't use it.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONSEQUENCES ACCOUNT
    # ============================================================================
    st.markdown("""
    ## 🧮 Consequences Account
    
    > 🌟 **Advanced feature**: Automatically track hidden costs.
    
    ### What is it?
    
    A rule system that automatically applies "consequences" (additional costs) to your expenses during month closing.
    
    ### Use Cases
    
    **Example 1: Taxes**
    - Rule: All **SUP** expenses have a 10% "psychological tax"
    - Effect: If you spend €100 on SUP, the system counts an extra €10 as consequence
    
    **Example 2: Nonsense Penalty**
    - Rule: Each **TON** expense generates a 50% penalty
    - Effect: Incentivizes reducing unnecessary expenses
    
    ### Configuration
    
    1. **Enable the feature**: **Utilities → Configuration → Consequences Account**
    2. **Create rules**: **Utilities → Consequences**
    
    Each rule has:
    - **Name**: Rule identifier
    - **Filters** (optional):
      - Relevance (NE/LI/SUP/TON)
      - Specific category
      - Concept (contains text)
    - **Action**:
      - **Percentage**: X% of the filtered expense
      - **Fixed Amount**: X€ for each expense that meets the filter
    
    ### When is it applied?
    
    When executing **Month Closing**, the system:
    1. Evaluates all active rules
    2. Calculates total consequences
    3. Creates an automatic **Investments/Savings** entry with that amount
    4. You can see it in the closing summary
    
    > 💡 **Tip**: Use this feature to force extra savings based on your habits.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # MONTH CLOSING FLOW
    # ============================================================================
    st.markdown("""
    ## 🔒 Month Closing
    
    Month closing is the heart of PersAcc.
    
    ### When to close?
    
    Once you receive next month's salary (even if it's the 28th), start closing the current month.
    
    ### Wizard Steps
    
    1. **Go to "Month Closing"** - The system automatically detects the next month to close
    
    2. **Enter bank balance** - The exact value showing in your account
       - *Traditional mode*: Balance **before** receiving salary
       - *Alternative mode*: Balance **after** receiving (configurable in settings)
    
    3. **Indicate salary** - The gross salary amount
    
    4. **Configure retentions**:
       - **% Surplus Retention**: From leftover money before salary
       - **% Salary Retention**: From new received salary
    
    5. **Review consequences** (if enabled):
       - The system shows the total consequences calculated according to your rules
       - This will be automatically added as investments/savings
    
    6. **Execute closing** - The system:
       - Creates automatic investments/savings entries (retentions + consequences)
       - Generates salary as income in the new month
       - Marks the month as CLOSED and immutable
       - Automatically switches to the next month
    
    ### Result
    
    Closed and immutable month + next month ready with correct starting balance.
    
    > 💡 **Tip**: You can disable automatic retentions in **Configuration** if you prefer manual management.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONFIGURATION
    # ============================================================================
    st.markdown("""
    ## ⚙️ Configuration
    
    Access from **Utilities → Configuration**.
    
    ### Available Options
    
    #### 🌐 Language & Currency
    
    | Setting | Options |
    |---------|---------|
    | **Language** | Español, English |
    | **Currency** | EUR, USD, GBP, CHF, JPY, CNY, MXN, ARS, COP, BRL |
    
    #### 🎛️ Features (Toggles)
    
    | Toggle | Description |
    |--------|-------------|
    | **Relevance Analysis** | NE/LI/SUP/TON system |
    | **Automatic Retentions** | Automatic investments/savings at closing |
    | **Consequences Account** | Advanced rule system |
    | **🤖 AI Analysis** | Smart comments with Ollama |
    
    #### 🤖 AI Configuration (Ollama)
    
    > Requires [Ollama](https://ollama.com/download) installed and running.
    
    | Setting | Description |
    |---------|-------------|
    | **Model** | Select from available models (tinyllama, phi3, mistral, llama3, qwen, etc.) |
    | **Status** | Green/red indicator of Ollama server status |
    
    #### 💰 Retentions
    
    | Setting | Description |
    |---------|-------------|
    | **% Surplus Retention** | Default value for wizard (0-100%) |
    | **% Salary Retention** | Default value for wizard (0-100%) |
    
    #### 📊 Closing Method
    
    | Method | Description |
    |--------|-------------|
    | **Before salary** | Enter balance BEFORE receiving salary (recommended) |
    | **After salary** | Enter balance AFTER receiving |
    
    #### 📝 Default Values
    
    Configure automatic values for each category:
    
    | Type | Description |
    |------|-------------|
    | **Default Concepts** | Text that auto-fills when selecting the category |
    | **Default Amounts** | Quantity that fills automatically |
    | **Default Relevance** | Predetermined NE/LI/SUP/TON code |
    
    > 💡 **Tip**: Configure default values for recurring expenses to save time.
    
    ### Configuration File
    
    Automatically saved in `data/config.json`.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # UTILITIES
    # ============================================================================
    st.markdown("""
    ## 🔧 Utilities
    
    ### Export CSV
    Download all LEDGER entries in CSV format for backup or external analysis.
    
    ### Import Legacy
    Import data from old CSV files:
    - **Expenses**: DATE, CONCEPT, CATEGORY, RELEVANCE, AMOUNT
    - **Income**: DATE, CONCEPT, AMOUNT
    - **Investments/Savings**: DATE, CONCEPT, AMOUNT, CATEGORY
    
    ### Clean DB
    - **Option 1**: Delete entries and closings (keeps categories)
    - **Option 2**: Total reset (regenerates everything from scratch)
    
    > ⚠️ **Important**: These actions are irreversible. Export a backup first.
    
    ### Category Management
    - Add, edit, or delete categories
    - Categories with history are archived instead of deleted
    - You can change the transaction type (EXPENSE→INVESTMENTS/SAVINGS, etc.)
    
    ### Consequences
    > Requires activation in Configuration
    
    Manage your consequence rules:
    - Create/edit/delete rules
    - Activate/deactivate specific rules
    - Changes apply on next month closing
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # DASHBOARD AND ANALYSIS
    # ============================================================================
    st.markdown("""
    ## 📊 Dashboard and Analysis
    
    ### Monthly View
    
    The main screen shows:
    - **Month KPIs**: Income, expenses, investments/savings, balance
    - **Transaction table**: Editable (if month is open)
    - **Relevance analysis**: NE/LI/SUP/TON distribution
    
    ### Historical
    
    Access from **History** to see:
    
    #### 📈 Global View
    - Accumulated year KPIs
    - Monthly evolution (area chart)
    - Current year vs historical average comparison
    
    #### 🔍 Deep Analysis
    - Top expenses of the year
    - Evolution by category
    - Most used words analysis in concepts
    - Curious metrics (average expense per day, etc.)
    
    #### 📋 Detailed Data
    - Complete table of year transactions
    - Filterable and exportable
    
    #### 📝 Annotations
    - Add personal notes per month or year
    - Remember decisions, context, or reflections
    - Shown in read-only mode when reviewing closed periods
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # ARTIFICIAL INTELLIGENCE
    # ============================================================================
    st.markdown("""
    ## 🤖 Artificial Intelligence (Ollama)
    
    PersAcc includes local AI integration using [Ollama](https://ollama.com).
    
    ### Requirements
    
    1. **Install Ollama**: Download from [ollama.com/download](https://ollama.com/download)
    2. **Download model**: Run `ollama pull phi3` (or tinyllama, mistral, llama3, qwen3)
    3. **Keep Ollama running**: The local server must be active
    
    ### AI Features
    
    #### 💬 Ledger Comment
    In monthly view, AI generates a witty comment about your month's finances.
    
    #### 📊 Period Analysis
    In Historical, generate deep analysis of selected month or year:
    - Spending patterns evaluation
    - Personalized recommendations
    - Category insights
    
    #### 💬 Chat Assistant
    Ask in natural language about your finances:
    - "How much did I spend on restaurants this month?"
    - "What are my biggest expenses in 2024?"
    - "Search for Uber expenses"
    
    ### Configuration
    
    1. Enable in **Utilities → Configuration → AI Analysis**
    2. Select model in **AI Model Configuration** section
    3. Green indicator confirms Ollama is working
    
    > 💡 **Recommended models**: phi3 (balanced), tinyllama (fast), mistral (quality)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # ML PROJECTIONS
    # ============================================================================
    st.markdown("""
    ## 📈 Projections (Machine Learning)
    
    Access from the **Projections** tab to see predictions based on your history.
    
    ### Projection Types
    
    #### 💰 Income Projection
    - Estimated salary evolution
    - Based on income history
    
    #### 📊 Investments/Savings Projection
    - Projected growth of invested capital
    - Considers automatic retentions
    
    #### 📉 Expense Projection
    - Future expense prediction
    - Analysis by category and seasonality
    
    ### Automatic Insights
    
    The system generates insights about your patterns:
    - Savings trends
    - Highest expense months
    - Wealth evolution
    
    > ⚠️ **Note**: Projections improve with more historical data. At least 6 months of history recommended.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS AND BEST PRACTICES
    # ============================================================================
    st.markdown("""
    ## 💡 Tips and Best Practices
    
    ### 📱 Daily Use
    1. **Record expenses daily** - 2 minutes in the morning with coffee
    2. **Use specific concepts** - "Target - Groceries" better than "Shopping"
    3. **Leverage auto-complete** - Configure default concepts to save time
    
    ### 📅 Weekly Use
    1. **Review dashboard** - Verify everything is properly categorized
    2. **Correct errors** - Use editable table if you made mistakes
    
    ### 🗓️ Monthly Use
    1. **Close when receiving salary** - Don't wait for the 1st of next month
    2. **Export backup** - Download CSV before closing
    3. **Review relevance analysis** - Adjust habits if necessary
    
    ### 🎯 Optimization
    1. **Adjust retentions** - According to your savings goals
    2. **Experiment with consequences** - Create rules that motivate you to improve
    3. **Disable what you don't use** - Simplify by disabling unnecessary features
    
    ### 🔒 Security
    1. **Regular backup** - Database is in `data/finanzas.db`
    2. **Version control** - Consider using Git to track changes
    3. **Portability** - All configuration is in local files
    
    ---
    
    **Version**: 3.0 | **Stack**: Streamlit + SQLite + Python + Ollama
    
    *Questions or suggestions? Open an issue in the repository.*
    """)
