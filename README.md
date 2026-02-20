# ETF Scraper Discord Bot

This bot scrapes holdings for QQQI, GPIQ, QYLD, and QDTE ETFs, stores them in a SQLite database, and generates daily reports.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

2.  **Environment Variables**:
    Create a `.env` file or export the following variable:
    ```bash
    export DISCORD_TOKEN="your_discord_bot_token"
    ```

## Usage

### Run the Scraper Manually
To run the scraper and generate reports without the bot:
```bash
python main.py
```
This will:
- Initialize the database (`etf_data.db`)
- Scrape the latest holdings
- Save data to the database
- Generate Markdown reports (e.g., `combined_report_YYYY-MM-DD.md`)

### Run the Discord Bot
```bash
python bot.py
```

## Discord Commands

- `!ping`: Check if bot is alive.
- `!latest_holdings <TICKER>`: Get the date and count of the latest data for an ETF.
- `!report <TICKER>`: Generate the latest daily report for an ETF (or `ALL`).
- `!scrape <TICKER>`: Trigger a manual scrape for an ETF (or `ALL`).

## Project Structure

- `bot.py`: Main Discord bot entry point.
- `main.py`: Standalone scraper and report generator.
- `config.py`: Configuration for URLs, ETFs, and paths.
- `database.py`: Database interactions (SQLite).
- `scrapers.py`: Scraper implementations using Requests and Playwright.
- `report.py`: Logic for comparing holdings and generating Markdown reports.
