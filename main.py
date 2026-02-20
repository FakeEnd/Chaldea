import sys
from datetime import datetime
import pandas as pd
from config import ETFS
from database import init_db, save_holdings, get_latest_date, get_holdings
from scrapers import QQQIScraper, GPIQScraper, QYLDScraper, QDTEScraper
from report import compare_holdings, analyze_options, generate_report, generate_options_only_report, generate_positions_only_report

def get_scraper(class_name):
    if class_name == "QQQIScraper": return QQQIScraper()
    if class_name == "GPIQScraper": return GPIQScraper()
    if class_name == "QYLDScraper": return QYLDScraper()
    if class_name == "QDTEScraper": return QDTEScraper()
    return None

def main():
    print("Initializing Database...")
    init_db()
    
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Running for date: {today}")

    # Target ETFs
    target_tickers = ["QQQI", "GPIQ", "QYLD", "QDTE"]
    all_reports = []
    all_options_reports = []
    all_positions_reports = []
    
    for ticker in target_tickers:
        if ticker not in ETFS:
            continue
            
        print(f"\nProcessing {ticker}...")
        
        # 1. Scrape
        scraper = get_scraper(ETFS[ticker]["scraper_class"])
        if not scraper:
            print(f"No scraper found for {ticker}")
            continue
            
        df_current = scraper.fetch_holdings()
        
        if df_current.empty:
            print(f"Failed to scrape {ticker}")
            continue
            
        print(f"Scraped {len(df_current)} records.")
        
        # 2. Get Previous Data
        last_date = get_latest_date(ticker)
        df_yesterday = None
        if last_date:
            print(f"Found previous data from {last_date}")
            df_yesterday = get_holdings(last_date, ticker)
        else:
            print("No history found.")

        # 3. Save Current Data
        save_holdings(today, ticker, df_current)
        
        # 4. Generate Report Sections
        diffs = compare_holdings(df_current, df_yesterday)
        opts_summary, lower, upper = analyze_options(df_current)
        
        # Standard report
        report_text = generate_report(today, ticker, diffs, opts_summary)
        all_reports.append(report_text)
        
        # Options-only report
        options_report_text = generate_options_only_report(today, ticker, diffs, opts_summary, df_current)
        all_options_reports.append(options_report_text)
        
        # Positions-only report (just the table)
        positions_report_text = generate_positions_only_report(today, ticker, df_current)
        all_positions_reports.append(positions_report_text)
        
        # Output progress to console
        print(f"Generated report sections for {ticker}")

    # 5. Save Combined Reports
    if all_reports:
        combined_filename = f"combined_report_{today}.md"
        with open(combined_filename, "w") as f:
            # Join reports with clear separators
            f.write("\n\n---\n\n".join(all_reports))
        print(f"\nSuccessfully generated combined report: {combined_filename}")
    else:
        print("\nNo reports generated.")
    
    if all_options_reports:
        options_filename = f"options_only_report_{today}.md"
        with open(options_filename, "w") as f:
            # Join options reports with clear separators
            f.write("\n\n---\n\n".join(all_options_reports))
        print(f"Successfully generated options-only report: {options_filename}")
    
    if all_positions_reports:
        positions_filename = f"positions_only_report_{today}.md"
        with open(positions_filename, "w") as f:
            # Join positions reports with clear separators
            f.write("\n\n---\n\n".join(all_positions_reports))
        print(f"Successfully generated positions-only report: {positions_filename}")

    # 6. Generate Image Reports
    print("\nGenerating Image Reports...")
    from visualizer import TableVisualizer
    
    # Store data for consolidated reports
    all_current_holdings = []
    all_diffs_collection = {'new': [], 'sold': [], 'increased': [], 'decreased': []}
    
    for ticker in target_tickers:
        if ticker not in ETFS: continue
        
        last_date = get_latest_date(ticker)
        if not last_date: continue
        
        df_current = get_holdings(last_date, ticker)
        # Add ETF ticker column for visualization
        df_current['etf_ticker'] = ticker
        
        # Get previous for changes
        import sqlite3
        conn = sqlite3.connect("etf_data.db")
        c = conn.cursor()
        c.execute(f"SELECT DISTINCT date FROM holdings_{ticker} ORDER BY date DESC LIMIT 2")
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        df_prev = None
        if len(dates) > 1:
            df_prev = get_holdings(dates[1], ticker)
        
        # 1. Positions Image
        display_df = df_current.copy()
        if df_prev is not None:
             merged = pd.merge(display_df, df_prev[['holding_ticker', 'shares']], on='holding_ticker', how='left', suffixes=('', '_prev'))
             merged['shares_prev'] = merged['shares_prev'].fillna(0)
             merged['shares_change'] = merged['shares'] - merged['shares_prev']
             display_df = merged
        else:
             display_df['shares_change'] = 0
             
        img_bytes = TableVisualizer.generate_image(display_df, title=f"{ticker} Holdings ({last_date})", date_str=last_date)
        if img_bytes:
            fname = f"positions_report_{ticker}_{last_date}.png"
            with open(fname, "wb") as f: f.write(img_bytes)
            print(f"Saved {fname}")

        # 2. Options Image
        img_bytes_opt = TableVisualizer.generate_options_image(df_current, title=f"{ticker} Options ({last_date})", date_str=last_date)
        if img_bytes_opt:
            fname = f"options_report_{ticker}_{last_date}.png"
            with open(fname, "wb") as f: f.write(img_bytes_opt)
            print(f"Saved {fname}")
            
        # 3. Changes Image
        diffs = compare_holdings(df_current, df_prev)
        # Add ETF ticker to diffs for aggregation
        for key in diffs:
            if not diffs[key].empty:
                diffs[key] = diffs[key].copy()
                diffs[key]['etf_ticker'] = ticker
                all_diffs_collection[key].append(diffs[key])
        
        img_bytes_chg = TableVisualizer.generate_changes_image(diffs, title=f"{ticker} Changes ({last_date})", date_str=last_date)
        if img_bytes_chg:
            fname = f"combined_report_{ticker}_{last_date}.png"
            with open(fname, "wb") as f: f.write(img_bytes_chg)
            print(f"Saved {fname}")

        # Collect for consolidated options report
        all_current_holdings.append(df_current)

    # 7. Generate Consolidated Reports
    if all_current_holdings:
        print("\nGenerating Consolidated Reports...")
        
        # Consolidated Options Report
        combined_df = pd.concat(all_current_holdings, ignore_index=True)
        img_bytes_all_opt = TableVisualizer.generate_options_image(combined_df, title=f"All ETFs Options ({today})", date_str=today)
        if img_bytes_all_opt:
            fname_all_opt = f"all_options_report_{today}.png"
            with open(fname_all_opt, "wb") as f: f.write(img_bytes_all_opt)
            print(f"Saved {fname_all_opt}")
            
        # Consolidated Changes Report
        # Merge lists of diffs
        combined_diffs = {}
        for key in all_diffs_collection:
            if all_diffs_collection[key]:
                combined_diffs[key] = pd.concat(all_diffs_collection[key], ignore_index=True)
            else:
                combined_diffs[key] = pd.DataFrame()
        
        img_bytes_all_chg = TableVisualizer.generate_changes_image(combined_diffs, title=f"All ETFs Changes ({today})", date_str=today)
        if img_bytes_all_chg:
            fname_all_chg = f"all_changes_report_{today}.png"
            with open(fname_all_chg, "wb") as f: f.write(img_bytes_all_chg)
            print(f"Saved {fname_all_chg}")

        # Consolidated Options Changes Report (User Request)
        # Filter combined_diffs for options
        options_diffs = {}
        has_options_changes = False
        
        for key in combined_diffs:
            df = combined_diffs[key]
            if not df.empty and 'asset_class' in df.columns:
                # Filter for 'Option' (exact case depends on scraper, usually 'Option' or 'Options')
                # Let's try flexible matching or just check scraper/db
                filtered = df[df['asset_class'].astype(str).str.contains('Option', case=False, na=False)]
                options_diffs[key] = filtered
                if not filtered.empty:
                    has_options_changes = True
            else:
                options_diffs[key] = pd.DataFrame()
        
        if has_options_changes:
            img_bytes_opt_chg = TableVisualizer.generate_changes_image(options_diffs, title=f"All ETFs Options Changes ({today})", date_str=today)
            if img_bytes_opt_chg:
                fname_opt_chg = f"all_options_changes_report_{today}.png"
                with open(fname_opt_chg, "wb") as f: f.write(img_bytes_opt_chg)
                print(f"Saved {fname_opt_chg}")
        else:
            print("No option changes detected for separate report.")

if __name__ == "__main__":
    main()
