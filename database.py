import sqlite3
import pandas as pd
from datetime import datetime
import os
from config import DB_PATH
from config import ETFS

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create separate tables for each ETF
    for ticker in ETFS.keys():
        table_name = f"holdings_{ticker}"
        c.execute(f'''CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            holding_ticker TEXT,
            description TEXT,
            shares REAL,
            market_value REAL,
            weight REAL,
            asset_class TEXT,
            strike_price REAL,
            expiration_date TEXT,
            option_type TEXT
        )''')
        
    conn.commit()
    conn.close()

def save_holdings(date, etf_ticker, df):
    conn = sqlite3.connect(DB_PATH)
    table_name = f"holdings_{etf_ticker}"
    
    # Check if data for this date already exists to avoid duplicates
    # We delete old data for the same date and re-insert
    c = conn.cursor()
    c.execute(f"DELETE FROM {table_name} WHERE date = ?", (date,))
    
    # Prepare dataframe for insertion
    # Ensure columns match schema
    # Schema: date, holding_ticker, description, shares, market_value, weight, asset_class, strike_price, expiration_date, option_type
    
    # Add date column if not present or ensure it matches
    df['date'] = date
    
    # Select and order columns
    cols_to_keep = [
        'date', 'holding_ticker', 'description', 'shares', 'market_value', 
        'weight', 'asset_class', 'strike_price', 'expiration_date', 'option_type'
    ]
    
    # Ensure all columns exist
    for col in cols_to_keep:
        if col not in df.columns:
            df[col] = None
            
    df_to_save = df[cols_to_keep]
    
    df_to_save.to_sql(table_name, conn, if_exists='append', index=False)
    
    conn.commit()
    conn.close()
    print(f"Saved {len(df)} records for {etf_ticker} on {date} into {table_name}")

def get_holdings(date, etf_ticker):
    conn = sqlite3.connect(DB_PATH)
    table_name = f"holdings_{etf_ticker}"
    try:
        query = f"SELECT * FROM {table_name} WHERE date = ?"
        df = pd.read_sql_query(query, conn, params=(date,))
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df

def get_latest_date(etf_ticker):
    conn = sqlite3.connect(DB_PATH)
    table_name = f"holdings_{etf_ticker}"
    c = conn.cursor()
    try:
        c.execute(f"SELECT MAX(date) FROM {table_name}")
        result = c.fetchone()
        return result[0] if result else None
    except Exception:
        return None
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
