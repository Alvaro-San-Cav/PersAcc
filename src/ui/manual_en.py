"""
Manual Page - PersAcc (English)
Renders the complete user manual for the application.
"""
import streamlit as st


def render_manual_en():
    """Renders the complete user manual in English."""
    st.markdown('<div class="main-header"><h1>📖 User Manual - PersAcc</h1></div>', unsafe_allow_html=True)
    
    # ============================================================================
    # INTRODUCTION
    # ============================================================================
    st.markdown("""
    ## 🎯 What is PersAcc?
    
    **PersAcc** is a personal accounting system with monthly closing, automatic savings retention, and spending quality analysis.
    
    ### Key Features
    
    - ✅ **Automatic Month Closing** - Wizard that calculates retentions and opens the next month
    - ✅ **Configurable Retentions** - Set savings % on surplus and salary
    - ✅ **Expense Classification** - NE/LI/SUP/TON system to analyze habits
    - ✅ **Editable Table** - Modify transactions with closed month validation
    - ✅ **Historical Dashboard** - Annual KPIs and monthly evolution
    - ✅ **Multi-language** - English and Spanish
    - ✅ **Multi-currency** - Configure your currency (€, $, £, etc.)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # MONTH CLOSING FLOW
    # ============================================================================
    st.markdown("""
    ## 🔒 Month Closing
    
    The monthly closing is the heart of PersAcc.
    
    ### When to close?
    
    Once you receive next month's salary (even on the 28th), start closing the current month.
    
    ### Wizard Steps
    
    1. **Go to "Month Closing"** - The system automatically detects the next month to close
    
    2. **Enter your bank balance** - The exact value shown in your account
       - *Traditional mode*: Balance **before** receiving salary
       - *Alternative mode*: Balance **after** receiving salary (configurable in settings)
    
    3. **Enter the salary** - The gross salary amount
    
    4. **Configure retentions**:
       - **% Surplus Retention**: From leftover money before salary
       - **% Salary Retention**: From the new salary received
    
    5. **Execute the closing** - The system:
       - Creates automatic investment entries
       - Generates salary as income in the new month
       - Automatically switches to the next month
    
    ### Result
    
    Closed and immutable month + next month ready with correct opening balance.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # ADDING MOVEMENTS
    # ============================================================================
    st.markdown("""
    ## ➕ Adding Movements
    
    ### Quick Add (Sidebar)
    
    The quick form in the sidebar lets you log expenses in seconds:
    
    1. Select the **type** (Expense, Income, Investment, Transfer)
    2. Choose the **category**
    3. Write the **concept**
    4. Select **relevance** (expenses only)
    5. Set **date** and **amount**
    6. Click **Save**
    
    > 💡 **Tip**: If you select a different month, the default date will be the 1st of that month.
    
    ### Editable Table
    
    In the "Ledger" tab you can edit existing movements:
    - Modify category, concept, amount and relevance
    - Select and delete multiple entries
    - Closed months are protected from editing
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # SPENDING RELEVANCE
    # ============================================================================
    st.markdown("""
    ## 🎯 Spending Relevance
    
    Classify each expense to analyze your behavior:
    
    | Code | Meaning | Examples |
    |------|---------|----------|
    | **NE** | Necessary | Food, rent, bills |
    | **LI** | Like it | Dinners with friends, gym, hobbies |
    | **SUP** | Superfluous | Extra clothing, decoration |
    | **TON** | Nonsense | Impulse purchases, unused subscriptions |
    
    ### Goal
    
    Analyze what % of your spending goes to each category. Ideal:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # CONFIGURATION
    # ============================================================================
    st.markdown("""
    ## ⚙️ Configuration
    
    Access from **Utilities → Configuration**.
    
    ### Available options
    
    | Setting | Description |
    |---------|-------------|
    | **Language** | English or Spanish |
    | **Currency** | EUR, USD, GBP, and more |
    | **% Surplus Retention** | Default value for wizard |
    | **% Salary Retention** | Default value for wizard |
    | **Closing Method** | Before or after receiving salary |
    | **Default concepts** | Suggested text per category |
    
    ### Configuration file
    
    Automatically saved in `data/config.json`.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # UTILITIES
    # ============================================================================
    st.markdown("""
    ## 🔧 Utilities
    
    ### Export CSV
    Download all LEDGER entries in CSV format for backup.
    
    ### Import Legacy
    Import data from CSV files (expenses, income, investments).
    
    ### Clean DB
    - Delete entries and closures (keeps categories)
    - Full reset (regenerates everything from scratch)
    
    ### Category Management
    Add, edit or delete categories. Those with history are archived instead of deleted.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS
    # ============================================================================
    st.markdown("""
    ## 💡 Tips
    
    1. **Log expenses daily** - 2 minutes in the morning
    2. **Review weekly** - Correct categories if needed
    3. **Close when you receive salary** - Don't wait until the 1st
    4. **Export monthly** - Keep a cloud backup
    5. **Use specific concepts** - "Walmart" instead of "Shopping"
    
    ---
    
    **Version**: 1.2 | **Stack**: Streamlit + SQLite + Python
    """)
