import discord
import sys
from discord.ext import commands
import os
import asyncio
import json
from datetime import datetime
from config import ETFS
from database import init_db, get_latest_date, get_holdings, save_holdings
from scrapers import QQQIScraper, GPIQScraper, QYLDScraper, QDTEScraper
from report import compare_holdings, analyze_options, generate_report, generate_options_only_report, generate_positions_only_report
import pandas as pd
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# Load environment variables
load_dotenv()

# Configuration File for Channel ID
CONFIG_FILE = "bot_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
scheduler = AsyncIOScheduler()

# Helper to get scraper instance
def get_scraper(class_name):
    if class_name == "QQQIScraper": return QQQIScraper()
    if class_name == "GPIQScraper": return GPIQScraper()
    if class_name == "QYLDScraper": return QYLDScraper()
    if class_name == "QDTEScraper": return QDTEScraper()
    return None

async def run_scheduled_task():
    """Function to run the daily scrape and report."""
    config = load_config()
    channel_id = config.get("daily_channel_id")
    
    if not channel_id:
        print("Scheduled task skipped: No channel set.")
        return

    channel = bot.get_channel(channel_id)
    if not channel:
        print(f"Scheduled task skipped: Channel {channel_id} not found.")
        return

    await channel.send("🕒 **Starting Daily Scheduled Task...**")

    # 1. Scrape
    await channel.send("🔄 Scraping latest data...")
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    target_tickers = list(ETFS.keys())
    
    for t in target_tickers:
        scraper = get_scraper(ETFS[t]["scraper_class"])
        if not scraper: continue
        
        try:
            df = await bot.loop.run_in_executor(None, scraper.fetch_holdings)
            if not df.empty:
                save_holdings(today, t, df)
                results.append(f"✅ {t}: Success ({len(df)} records)")
            else:
                results.append(f"❌ {t}: Failed (Empty Data)")
        except Exception as e:
            results.append(f"⚠️ {t}: Error ({str(e)})")
            
    await channel.send("Scrape Results:\n" + "\n".join(results))

    # 2. Report
    await channel.send("📊 Generating Daily Reports...")
    
    # We reuse the logic from the report command, but customized for the channel
    # Generate "ALL OPTIONS CHANGES" and "ALL CHANGES" equivalent
    
    all_current_holdings = []
    all_diffs_collection = {'new': [], 'sold': [], 'increased': [], 'decreased': []}
    
    from visualizer import TableVisualizer
    import io
    import sqlite3
    from config import DB_PATH

    for t in target_tickers:
        latest_date = get_latest_date(t)
        if not latest_date: continue
            
        df_current = get_holdings(latest_date, t)
        df_current['etf_ticker'] = t
        
        # Get Previous
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"SELECT DISTINCT date FROM holdings_{t} ORDER BY date DESC LIMIT 2")
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        df_prev = None
        if len(dates) > 1:
            df_prev = get_holdings(dates[1], t)

        diffs = compare_holdings(df_current, df_prev)
        all_current_holdings.append(df_current)
        
        for key in diffs:
            if not diffs[key].empty:
                d = diffs[key].copy()
                d['etf_ticker'] = t
                all_diffs_collection[key].append(d)

    # Consolidated Options Report
    if all_current_holdings:
        combined_df = pd.concat(all_current_holdings, ignore_index=True)
        img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_options_image(combined_df, title=f"All ETFs Options ({today})", date_str=today))
        if img: await channel.send(file=discord.File(io.BytesIO(img), filename=f"all_options_{today}.png"))

    # Consolidated Changes Report
    combined_diffs = {}
    for key in all_diffs_collection:
        if all_diffs_collection[key]:
            combined_diffs[key] = pd.concat(all_diffs_collection[key], ignore_index=True)
        else:
            combined_diffs[key] = pd.DataFrame()

    img_changes = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_changes_image(combined_diffs, title=f"All ETFs Changes ({today})", date_str=today))
    if img_changes: await channel.send(file=discord.File(io.BytesIO(img_changes), filename=f"all_changes_{today}.png"))

    await channel.send("✅ **Daily Task Complete!**")


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    init_db()
    print("Database initialized.")
    
    # Start Scheduler
    # Schedule: Monday-Friday at 5:00 PM ET (17:00)
    # Using 'US/Eastern' timezone
    trigger = CronTrigger(day_of_week='mon-fri', hour=17, minute=0, timezone=pytz.timezone('US/Eastern'))
    scheduler.add_job(run_scheduled_task, trigger)
    scheduler.start()
    print("Scheduler started: Mon-Fri at 5:00 PM ET")

@bot.command(name='set_daily_channel')
async def set_daily_channel(ctx):
    """Sets the current channel for daily reports."""
    config = load_config()
    config["daily_channel_id"] = ctx.channel.id
    save_config(config)
    await ctx.send(f"✅ Daily reports will now be posted in {ctx.channel.mention}")

@bot.command(name='test_schedule')
async def test_schedule(ctx):
    """Force run the scheduled task now."""
    await ctx.send("Force running scheduled task...")
    await run_scheduled_task()

@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command(name='latest_holdings')
async def latest_holdings(ctx, ticker: str):
    """Get the latest holdings count and date for a specific ETF."""
    ticker = ticker.upper()
    if ticker not in ETFS:
        await ctx.send(f"Unknown ETF ticker: {ticker}. Available: {', '.join(ETFS.keys())}")
        return

    latest_date = get_latest_date(ticker)
    if not latest_date:
        await ctx.send(f"No data found for {ticker}.")
        return

    df = get_holdings(latest_date, ticker)
    await ctx.send(f"**{ticker}**\nLatest Date: {latest_date}\nTotal Holdings: {len(df)}\n")

@bot.command(name='report')
async def report(ctx, ticker: str = "ALL", report_type: str = "ALL"):
    """
    Generate reports.
    Usage: 
      !report QQQI
      !report ALL
      !report ALL OPTIONS
      !report ALL CHANGES
      !report ALL OPTIONS_CHANGES
    """
    ticker = ticker.upper()
    report_type = report_type.upper()
    
    # Validate report_type
    valid_types = ["ALL", "OPTIONS", "CHANGES", "OPTIONS_CHANGES", "POSITIONS"]
    if report_type not in valid_types:
        await ctx.send(f"Invalid report type: {report_type}. Valid types: {', '.join(valid_types)}")
        return

    target_tickers = [ticker] if ticker != "ALL" else list(ETFS.keys())
    today = datetime.now().strftime('%Y-%m-%d')
    
    await ctx.send(f"Generating {report_type} report for {ticker}...")
    
    # Accumulators for consolidated reports
    all_current_holdings = []
    all_diffs_collection = {'new': [], 'sold': [], 'increased': [], 'decreased': []}
    
    from visualizer import TableVisualizer
    import io
    import pandas as pd
    import sqlite3
    from config import DB_PATH

    # 1. Collect Data & Generate Individual Reports
    for t in target_tickers:
        if t not in ETFS: continue
            
        latest_date = get_latest_date(t)
        if not latest_date:
            if ticker != "ALL": await ctx.send(f"No data found for {t}.")
            continue
            
        # Get Current
        df_current = get_holdings(latest_date, t)
        df_current['etf_ticker'] = t # Add ETF column
        
        # Get Previous
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(f"SELECT DISTINCT date FROM holdings_{t} ORDER BY date DESC LIMIT 2")
        dates = [row[0] for row in c.fetchall()]
        conn.close()
        
        df_prev = None
        if len(dates) > 1:
            df_prev = get_holdings(dates[1], t)

        # Process Changes
        diffs = compare_holdings(df_current, df_prev)
        
        # Collect for consolidated
        all_current_holdings.append(df_current)
        for key in diffs:
            if not diffs[key].empty:
                d = diffs[key].copy()
                d['etf_ticker'] = t
                all_diffs_collection[key].append(d)

        # Generate Individual Reports IF ticker is NOT ALL
        if ticker != "ALL":
            # 1. Positions Report
            if report_type in ["ALL", "POSITIONS"]:
                display_df = df_current.copy()
                if df_prev is not None:
                     merged = pd.merge(display_df, df_prev[['holding_ticker', 'shares']], on='holding_ticker', how='left', suffixes=('', '_prev'))
                     merged['shares_prev'] = merged['shares_prev'].fillna(0)
                     merged['shares_change'] = merged['shares'] - merged['shares_prev']
                     display_df = merged
                else:
                     display_df['shares_change'] = 0
                
                # Run visualizer in executor
                img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_image(display_df, title=f"{t} Holdings ({latest_date})", date_str=latest_date))
                if img: await ctx.send(file=discord.File(io.BytesIO(img), filename=f"{t}_positions.png"))

            # 2. Options Report
            if report_type in ["ALL", "OPTIONS"]:
                img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_options_image(df_current, title=f"{t} Options ({latest_date})", date_str=latest_date))
                if img: await ctx.send(file=discord.File(io.BytesIO(img), filename=f"{t}_options.png"))

            # 3. Changes Report
            if report_type in ["ALL", "CHANGES"]:
                img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_changes_image(diffs, title=f"{t} Changes ({latest_date})", date_str=latest_date))
                if img: await ctx.send(file=discord.File(io.BytesIO(img), filename=f"{t}_changes.png"))
                
            # 4. Options Changes Report
            if report_type in ["ALL", "OPTIONS_CHANGES"]:
                opt_diffs = {}
                has_opt = False
                for k, v in diffs.items():
                    if not v.empty and 'asset_class' in v.columns:
                        filt = v[v['asset_class'].astype(str).str.contains('Option', case=False, na=False)]
                        opt_diffs[k] = filt
                        if not filt.empty: has_opt = True
                    else:
                        opt_diffs[k] = pd.DataFrame()
                
                if has_opt:
                    img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_changes_image(opt_diffs, title=f"{t} Options Changes ({latest_date})", date_str=latest_date))
                    await ctx.send(file=discord.File(io.BytesIO(img), filename=f"{t}_opt_changes.png"))

    # 2. Generate Consolidated Reports IF ticker is ALL
    if ticker == "ALL":
        if not all_current_holdings:
            await ctx.send("No data available for consolidated reports.")
            return

        # Consolidated Options
        if report_type in ["ALL", "OPTIONS"]:
            combined_df = pd.concat(all_current_holdings, ignore_index=True)
            img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_options_image(combined_df, title=f"All ETFs Options ({today})", date_str=today))
            if img: await ctx.send(file=discord.File(io.BytesIO(img), filename="all_options.png"))

        # Consolidated Changes
        combined_diffs = {}
        for key in all_diffs_collection:
            if all_diffs_collection[key]:
                combined_diffs[key] = pd.concat(all_diffs_collection[key], ignore_index=True)
            else:
                combined_diffs[key] = pd.DataFrame()

        if report_type in ["ALL", "CHANGES"]:
            img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_changes_image(combined_diffs, title=f"All ETFs Changes ({today})", date_str=today))
            if img: await ctx.send(file=discord.File(io.BytesIO(img), filename="all_changes.png"))

        # Consolidated Options Changes
        if report_type in ["ALL", "OPTIONS_CHANGES"]:
            options_diffs = {}
            has_opt_changes = False
            for key in combined_diffs:
                df = combined_diffs[key]
                if not df.empty and 'asset_class' in df.columns:
                    filtered = df[df['asset_class'].astype(str).str.contains('Option', case=False, na=False)]
                    options_diffs[key] = filtered
                    if not filtered.empty: has_opt_changes = True
                else:
                    options_diffs[key] = pd.DataFrame()
            
            if has_opt_changes:
                img = await bot.loop.run_in_executor(None, lambda: TableVisualizer.generate_changes_image(options_diffs, title=f"All ETFs Options Changes ({today})", date_str=today))
                if img: await ctx.send(file=discord.File(io.BytesIO(img), filename="all_opt_changes.png"))
            else:
                 await ctx.send("No option changes detected across all ETFs.")

@bot.command(name='scrape')
async def scrape(ctx, ticker: str = "ALL"):
    """
    Manually trigger scraping.
    Usage: !scrape QQQI or !scrape ALL
    """
    ticker = ticker.upper()
    target_tickers = [ticker] if ticker != "ALL" else list(ETFS.keys())
    
    await ctx.send(f"Starting scrape for: {', '.join(target_tickers)}...")
    
    today = datetime.now().strftime('%Y-%m-%d')
    results = []
    
    for t in target_tickers:
        if t not in ETFS: 
            results.append(f"{t}: Invalid Ticker")
            continue
            
        scraper = get_scraper(ETFS[t]["scraper_class"])
        if not scraper:
            results.append(f"{t}: No scraper defined")
            continue
            
        try:
            # Run blocking code in executor to avoid freezing bot
            df = await bot.loop.run_in_executor(None, scraper.fetch_holdings)
            
            if not df.empty:
                save_holdings(today, t, df)
                results.append(f"{t}: Success ({len(df)} records)")
            else:
                results.append(f"{t}: Failed (Empty Data)")
        except Exception as e:
            results.append(f"{t}: Error ({str(e)})")
            
    await ctx.send("Scrape complete:\n" + "\n".join(results))

# Run the bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("Error: DISCORD_TOKEN environment variable not set.")
        sys.exit(1)
    bot.run(TOKEN)
