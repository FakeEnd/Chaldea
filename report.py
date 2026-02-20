import pandas as pd
from datetime import datetime, timedelta
from config import ETFS

def compare_holdings(today_df, yesterday_df):
    """
    Compare two dataframes of holdings.
    Returns a dictionary with 'new', 'sold', 'increased', 'decreased', 'unchanged' dataframes.
    """
    if yesterday_df is None or yesterday_df.empty:
        return {
            'new': today_df,
            'sold': pd.DataFrame(columns=today_df.columns),
            'increased': pd.DataFrame(columns=today_df.columns),
            'decreased': pd.DataFrame(columns=today_df.columns),
            'unchanged': pd.DataFrame(columns=today_df.columns)
        }

    # Ensure unique key for merge (Ticker)
    # If ticker is missing, use Description? Better to rely on Ticker if possible.
    
    # Merge on holding_ticker
    merged = pd.merge(
        today_df, 
        yesterday_df, 
        on='holding_ticker', 
        how='outer', 
        suffixes=('_today', '_yesterday'),
        indicator=True
    )
    
    # New Positions (Left only)
    new_holdings = merged[merged['_merge'] == 'left_only'].copy()
    # Clean up columns
    for col in today_df.columns:
        if col + '_today' in new_holdings.columns:
            new_holdings[col] = new_holdings[col + '_today']
    new_holdings = new_holdings[today_df.columns]

    # Sold Positions (Right only)
    sold_holdings = merged[merged['_merge'] == 'right_only'].copy()
    for col in today_df.columns:
        if col + '_yesterday' in sold_holdings.columns:
            sold_holdings[col] = sold_holdings[col + '_yesterday']
    sold_holdings = sold_holdings[today_df.columns]

    # Commons
    common = merged[merged['_merge'] == 'both'].copy()
    
    # Calculate Change in Shares
    common['shares_change'] = common['shares_today'] - common['shares_yesterday']
    
    increased = common[common['shares_change'] > 0].copy()
    decreased = common[common['shares_change'] < 0].copy()
    unchanged = common[common['shares_change'] == 0].copy()
    
    # Restore standard columns for report
    for df_subset in [increased, decreased, unchanged]:
        for col in today_df.columns:
            if col + '_today' in df_subset.columns:
                df_subset[col] = df_subset[col + '_today']
        # Keep shares_change
    
    return {
        'new': new_holdings,
        'sold': sold_holdings,
        'increased': increased,
        'decreased': decreased,
        'unchanged': unchanged
    }

def analyze_options(df):
    """
    Analyze options positions to determine upper and lower bounds.
    Assumes NEOS/Income ETFs sell covered calls (Upper Bound) or Puts (Lower Bound).
    """
    options = df[df['asset_class'] == 'Option'].copy()
    
    if options.empty:
        return "No Options Positions Found", None, None

    # Sort by expiration
    options['expiration_date'] = pd.to_datetime(options['expiration_date'], errors='coerce')
    options = options.sort_values('expiration_date')
    
    report_lines = []
    
    # Group by Expiration
    lower_bound = None
    upper_bound = None
    
    for exp_date, group in options.groupby('expiration_date'):
        exp_str = exp_date.strftime('%Y-%m-%d') if pd.notnull(exp_date) else "Unknown Date"
        header = f"### Expiration: {exp_str}"
        report_lines.append(header)
        
        calls = group[group['option_type'] == 'Call']
        puts = group[group['option_type'] == 'Put']
        
        # In Income ETFs:
        # Short Call usually defines the Capped Upside (Upper Bound)
        # Short Put usually defines the entry point or Lower Bound
        # But QQQI might be different (Call Spread? Just Short Call?)
        
        if not calls.empty:
            # Assuming short calls (negative shares? or just presence in this list implies short for these ETFs?)
            # Usually holdings show positive shares for long, negative for short?
            # Or just list the position.
            # Let's assume the ETF writes calls.
            # Max strike call is the cap? Or min strike call?
            # Usually they sell OTM calls.
            
            # Simple Stat: Range of Strikes
            min_call = calls['strike_price'].min()
            max_call = calls['strike_price'].max()
            report_lines.append(f"- Calls: Strike Range {min_call} - {max_call}")
            
            if upper_bound is None: upper_bound = min_call # Conservative cap

        if not puts.empty:
            min_put = puts['strike_price'].min()
            max_put = puts['strike_price'].max()
            report_lines.append(f"- Puts: Strike Range {min_put} - {max_put}")
            
            if lower_bound is None: lower_bound = max_put # Conservative floor
            
    summary = "\n".join(report_lines)
    return summary, lower_bound, upper_bound

def generate_report(today_date, etf_ticker, diffs, options_summary):
    """
    Generate a markdown report string.
    """
    report = []
    report.append(f"# Daily Holdings Report: {etf_ticker} ({today_date})")
    
    # Options Section
    report.append("## Options Analysis (Bounds)")
    if options_summary[0]:
        report.append(options_summary[0])
        report.append(f"\n**Estimated Lower Bound:** {options_summary[1]}")
        report.append(f"**Estimated Upper Bound:** {options_summary[2]}")
    else:
        report.append("No options data available.")

    # Changes Section
    report.append("\n## Position Changes")
    
    if not diffs['new'].empty:
        report.append(f"### 🟢 New Positions ({len(diffs['new'])})")
        report.append(diffs['new'][['holding_ticker', 'description', 'shares', 'weight']].to_markdown(index=False))
    
    if not diffs['sold'].empty:
        report.append(f"### 🔴 Sold Positions ({len(diffs['sold'])})")
        report.append(diffs['sold'][['holding_ticker', 'description', 'shares']].to_markdown(index=False))
        
    if not diffs['increased'].empty:
        report.append(f"### 🔼 Increased Positions ({len(diffs['increased'])})")
        # specific formatting for readability
        view = diffs['increased'][['holding_ticker', 'description', 'shares_today', 'shares_change']]
        report.append(view.head(10).to_markdown(index=False))
        if len(view) > 10: report.append(f"... and {len(view)-10} more.")

    if not diffs['decreased'].empty:
        report.append(f"### 🔽 Decreased Positions ({len(diffs['decreased'])})")
        view = diffs['decreased'][['holding_ticker', 'description', 'shares_today', 'shares_change']]
        report.append(view.head(10).to_markdown(index=False))
        if len(view) > 10: report.append(f"... and {len(view)-10} more.")

    return "\n".join(report)

def generate_options_only_report(today_date, etf_ticker, diffs, options_summary, current_df):
    """
    Generate a markdown report focused exclusively on options positions.
    Filters out all equity/stock holdings and only shows option-related changes.
    """
    report = []
    report.append(f"# Options-Only Report: {etf_ticker} ({today_date})")
    
    # Current Options Positions
    report.append("\n## Current Options Positions")
    options_df = current_df[current_df['asset_class'] == 'Option'].copy()
    
    if not options_df.empty:
        # Select relevant columns for options display
        # Use market_value for GPIQ, shares for others
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value', 'weight']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares', 'weight']
        
        available_cols = [col for col in display_cols if col in options_df.columns]
        report.append(options_df[available_cols].to_markdown(index=False))
        report.append(f"\n**Total Options Positions:** {len(options_df)}")
    else:
        report.append("No current options positions.")
    
    # Options Changes Section
    report.append("\n## Options Position Changes")
    
    # Filter each diff category to only include options
    new_options = diffs['new'][diffs['new']['asset_class'] == 'Option'] if 'asset_class' in diffs['new'].columns else pd.DataFrame()
    sold_options = diffs['sold'][diffs['sold']['asset_class'] == 'Option'] if 'asset_class' in diffs['sold'].columns else pd.DataFrame()
    increased_options = diffs['increased'][diffs['increased']['asset_class'] == 'Option'] if 'asset_class' in diffs['increased'].columns else pd.DataFrame()
    decreased_options = diffs['decreased'][diffs['decreased']['asset_class'] == 'Option'] if 'asset_class' in diffs['decreased'].columns else pd.DataFrame()
    
    if not new_options.empty:
        report.append(f"### 🟢 New Options ({len(new_options)})")
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares']
        available_cols = [col for col in display_cols if col in new_options.columns]
        report.append(new_options[available_cols].to_markdown(index=False))
    
    if not sold_options.empty:
        report.append(f"### 🔴 Closed Options ({len(sold_options)})")
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares']
        available_cols = [col for col in display_cols if col in sold_options.columns]
        report.append(sold_options[available_cols].to_markdown(index=False))
        
    if not increased_options.empty:
        report.append(f"### 🔼 Increased Options ({len(increased_options)})")
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares_today', 'shares_change']
        available_cols = [col for col in display_cols if col in increased_options.columns]
        report.append(increased_options[available_cols].to_markdown(index=False))

    if not decreased_options.empty:
        report.append(f"### 🔽 Decreased Options ({len(decreased_options)})")
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares_today', 'shares_change']
        available_cols = [col for col in display_cols if col in decreased_options.columns]
        report.append(decreased_options[available_cols].to_markdown(index=False))
    
    if new_options.empty and sold_options.empty and increased_options.empty and decreased_options.empty:
        report.append("No options position changes detected.")

    return "\n".join(report)

def generate_positions_only_report(today_date, etf_ticker, current_df):
    """
    Generate a minimal report showing ONLY the current options positions table.
    No analysis, no changes, just the positions.
    """
    report = []
    report.append(f"# Options Positions: {etf_ticker} ({today_date})")
    
    options_df = current_df[current_df['asset_class'] == 'Option'].copy()
    
    if not options_df.empty:
        # Select relevant columns for options display
        # Use market_value for GPIQ, shares for others
        if etf_ticker == 'GPIQ':
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'market_value', 'weight']
        else:
            display_cols = ['holding_ticker', 'description', 'option_type', 'strike_price', 'expiration_date', 'shares', 'weight']
        
        available_cols = [col for col in display_cols if col in options_df.columns]
        report.append(options_df[available_cols].to_markdown(index=False))
        report.append(f"\n**Total Options Positions:** {len(options_df)}")
    else:
        report.append("No current options positions.")

    return "\n".join(report)
