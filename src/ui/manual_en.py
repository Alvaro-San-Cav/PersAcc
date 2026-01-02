"""
Manual Page - PersAcc (English Version)
Renders the complete user manual with detailed documentation.
"""
import streamlit as st


def render_manual_en():
    """Renders the complete user manual in English."""
    st.markdown('<div class="main-header"><h1>📖 PersAcc Complete Manual</h1></div>', unsafe_allow_html=True)
    
    # ============================================================================
    # INTRODUCTION
    # ============================================================================
    st.markdown("""
    ## 🎯 What is PersAcc?
    
    **PersAcc** (Personal Accounting) is a personal accounting system designed to give you total control over your monthly finances. Unlike simple expense tracking apps, PersAcc implements a **complete accounting methodology** that allows you to:
    
    - **Close fiscal months** in an orderly manner, creating immutable snapshots of your financial situation
    - **Automate savings and investment** through configurable retentions when closing each month
    - **Classify expenses by relevance** (Necessary, I like it, Superfluous, Nonsense) to analyze your financial behavior
    - **Maintain complete and immutable history** of all your financial movements with referential integrity
    
    **Core Philosophy**: The system assumes you are disciplined with savings. When closing each month, you define what percentage of the remaining balance and your next salary goes to investment/savings. These amounts are automatically recorded as movements, reducing your "operational balance" (the money actually available to spend).
    
    PersAcc is **NOT**:
    - ❌ An investment manager (doesn't track asset returns)
    - ❌ A rigid budgeter (doesn't limit spending by category)
    - ❌ A banking app (doesn't connect to your bank or make payments)
    
    PersAcc **IS**:
    - ✅ Your personal ledger in digital format
    - ✅ A monthly closing system with automatic retentions
    - ✅ A spending habits analysis tool
    - ✅ Your single source of truth about your monthly financial situation
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # MONTH CLOSING FLOW
    # ============================================================================
    st.markdown("""
    ## 🔒 Month Closing Flow (The Heart of the System)
    
    Month closing is the most important process in PersAcc. When you close a month:
    1. All information from that period is "frozen" (you won't be able to edit it)
    2. Savings/investment retentions are automatically calculated
    3. Your next salary entry is generated in the new month
    4. The following month automatically opens with the correct initial balance
    
    ### 📅 Detailed Closing Mechanics
    
    #### Pre-step: Verification
    - **Strict linearity**: You can only close months in order. If you close January, you MUST close February next (you can't skip to March)
    - **One chance only**: Once a month is closed, it's immutable. If you make a mistake, you need to contact support or modify the DB directly
    
    #### Step 1: Capture Real Bank Balance
    **What do you enter?** The money you **actually have** in your bank account **right now**, BEFORE receiving the next salary.
    
    **Why is it important?** This value is used to:
    - Verify that your records match reality
    - Calculate the "surplus" (money left over from the month)
    - Detect discrepancies between what's recorded and what's real
    
    #### Step 2: Configure New Salary
    **What do you enter?** The **gross** amount of the salary you'll receive soon (for the following month).
    
    **What does the system do?**
    - Creates an INCOME entry in the "Salary" category dated 01/MM+1
    - This income will already appear in the new month that opens after closing
    
    #### Step 3: Define Retentions
    
    **Surplus Retention** (money left over this month):
    - The system calculates: `Surplus = Real Balance - Sum of all month expenses/investments`
    - You decide what % to retain (e.g.: 50% of €300 = €150 to investment)
    - An INVESTMENT entry is automatically created in the "Surplus retention investment" category dated end of current month
    
    **Salary Retention** (from the new salary):
    - You decide what % of salary to allocate to savings/investment (e.g.: 20% of €2,500 = €500)
    - An INVESTMENT entry is automatically created in the "Salary retention investment" category dated 01/MM+1 (next month)
    
    #### Step 4: Confirmation and Execution
    Upon confirming the closing:
    1. ✅ Month is marked as CLOSED (immutable)
    2. 📊 A snapshot is created with all calculated KPIs
    3. 💰 Salary entry is generated in the new month
    4. 📈 Investment entries are generated for retentions
    5. 🔓 The following month automatically opens to start recording expenses
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # DEFAULT CONFIGURATION
    # ============================================================================
    st.markdown("""
    ## ⚙️ Default Values Configuration
    
    ### What are defaults for?
    
    Default values save you time when recording frequent transactions and closing months. PersAcc stores your configuration in `data/config.json`.
    
    ### How to configure (step by step)
    
    1. **Access configuration**:
       - Go to the "🔧 Utilities" tab
       - Select the "⚙️ Configuration" sub-tab
    
    2. **Default retentions**:
       - **% Surplus Retention**: Suggested value when closing month (e.g.: 50%)
       - **% Salary Retention**: Suggested value for salary investment (e.g.: 20%)
       
       These values will appear pre-filled in the closing wizard, but you can always change them manually.
    
    3. **Default concepts by category**:
       
       For each active category, you can define text that auto-fills in the "Concept" field when using Quick Add.
       
       **Useful example**:
       - "Food" category → Default concept: "Supermarket"
       - "Transport" category → Default concept: "Gas"
       - "Restaurants" category → Default concept: "Eating out"
    
    4. **Save changes**:
       - Click "💾 Save Configuration"
       - Changes apply immediately (no need to restart the app)
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # DATA IMPORT
    # ============================================================================
    st.markdown("""
    ## 📥 Data Import from Other Sources
    
    ### What can you import?
    
    PersAcc allows importing legacy data from CSV files. This is useful if you:
    - Migrate from another finance app (Excel, YNAB, Mint, etc.)
    - Have bank statements in CSV
    - Want to do a "bulk import" of historical movements
    
    ### Supported Formats (CSV)
    
    #### Format 1: EXPENSES
    ```csv
    DATE,CONCEPT,CATEGORY,RELEVANCE,AMOUNT
    01/01/2025,Carrefour Supermarket,Food,NE,45.30
    05/01/2025,Dinner with friends,Restaurants,LI,32.50
    10/01/2025,Netflix,Subscriptions,SUP,13.99
    ```
    
    **Column descriptions**:
    - `DATE`: Date in DD/MM/YYYY format
    - `CONCEPT`: Free text describing the expense
    - `CATEGORY`: Category name (must exist in your DB)
    - `RELEVANCE`: Relevance code (`NE`, `LI`, `SUP`, `TON`)
    - `AMOUNT`: Amount in euros (use `.` for decimals)
    
    #### Format 2: INCOME
    ```csv
    DATE,CONCEPT,AMOUNT
    01/01/2025,January Salary,2500.00
    15/01/2025,Freelance project X,450.00
    ```
    
    #### Format 3: INVESTMENTS
    ```csv
    DATE,CONCEPT,AMOUNT,CATEGORY
    01/05/2025,Fund M contribution,500.00,Investment
    15/05/2025,ETF purchase,200.00,Investment
    ```
    
    ### How to import (step by step)
    
    1. **Prepare your CSV**:
       - Make sure it follows one of the supported formats
       - Encoding: UTF-8 (important for special characters)
       - Separator: comma (`,`)
    
    2. **Access import**:
       - Tab "🔧 Utilities" → Sub-tab "📥 Import Legacy"
    
    3. **Select type**:
       - "🔴 Expenses", "🟢 Income", or "🟣 Investments"
    
    4. **Upload your file**:
       - Click "Browse files" or drag the CSV
    
    5. **Preview**:
       - The system shows the first 5 rows
       - Verify they look correct
    
    6. **Execute import**:
       - Click "🚀 Execute Import"
       - The system uses `migration.py` internally
       - You'll see a log of operations performed
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # ADVANCED CONCEPTS
    # ============================================================================
    st.markdown("""
    ## 🧠 Advanced Concepts
    
    ### Fiscal Month
    
    The **fiscal month** in PersAcc coincides with the natural (calendar) month. Each transaction is recorded in the month it actually occurs.
    
    **Example**:
    - A transaction from January 28 → recorded in January
    - A transaction from February 1 → recorded in February
    
    ### Expense Relevance
    
    **NE (Necessary)**:
    - Essential expenses for living
    - Examples: food, rent, bills, commute transport
    
    **LI (I like it)**:
    - Expenses that bring you happiness/wellbeing
    - Examples: dinners with friends, hobbies, gym, books
    
    **SUP (Superfluous)**:
    - Not essential but occasionally justifiable
    - Examples: new clothes, decoration, unnecessary upgrades
    
    **TON (Nonsense)**:
    - Impulse purchases or regretted
    - Examples: boredom shopping, unused subscriptions
    
    **Goal**: Analyze what % of your expenses goes to each category. Ideally:
    - NE: 50-60%
    - LI: 20-30%
    - SUP: 10-15%
    - TON: < 5%
    
    ### Referential Integrity
    
    **What does it mean?** Closed months are immutable. If you try to edit/delete a movement from a closed month, the system rejects it.
    
    **Why?** Ensures your monthly snapshots always reflect the reality of that moment. You can't "cheat" by modifying the past.
    """)
    
    st.markdown("---")
    
    # ============================================================================
    # TIPS AND BEST PRACTICES
    # ============================================================================
    st.markdown("""
    ## 💡 Tips and Best Practices
    
    ### Recommended Daily Workflow
    
    1. **In the morning** (2 min):
       - Review receipts/bank notifications from previous day
       - Record expenses using Quick Add
    
    2. **Weekend** (5 min):
       - Review month's movements table
       - Correct categories or relevance if necessary
       - Verify nothing is missing
    
    3. **End of month** (10 min):
       - Compare real bank balance with "Current Balance" in PersAcc
       - If they match or are close → Close the month
       - If there's discrepancy → Find missing transactions
    
    ### Maximize Use of Defaults
    
    - Configure default concepts for your 10 most used categories
    - Adjust default retention % to the level you want to maintain
    - Use Quick Add for 90% of transactions (fast form)
    - Use editable table only for corrections
    
    ### Export Regularly
    
    - Once a month, export your complete LEDGER to CSV
    - Store it in the cloud (Google Drive, Dropbox)
    - It's your backup if something fails with the DB
    
    ### Monthly Analysis
    
    After closing each month, review:
    - **Balance**: Did you save or spend more than what came in?
    - **Spending quality**: What % was NE vs TON?
    - **Top categories**: Where did most money go?
    - **Trends**: Compare with previous months in the "History" tab
    
    ### Smart Categorization
    
    **Bad example**:
    - 50 ultra-specific categories ("Starbucks Coffee", "Local Coffee", "Machine Coffee"...)
    
    **Good example**:
    - 15-20 general categories ("Restaurants & Cafés")
    - Use the "Concept" field for specific details
    
    **Benefit**: Clearer graphs and analyses
    
    ---
    
    ## 📞 Support and Resources
    
    - **Source code**: [GitHub - PersAcc](https://github.com/your-repo) _(if open source)_
    - **Database**: SQLite in `data/finanzas.db`
    - **Logs**: Errors appear in console where you run `streamlit run app.py`
    
    **Current version**: 2.0  
    **Last update**: January 2026
    
    ---
    
    _Missing topics in this manual? Contribute by improving the documentation!_
    """)
