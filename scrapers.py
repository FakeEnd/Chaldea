import requests
import pandas as pd
import io
import time
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime
from config import USER_AGENT, QQQI_AJAX_URL, GPIQ_HOLDINGS_URL, QYLD_HOLDINGS_URL_BASE, QDTE_HOLDINGS_URL
from playwright.sync_api import sync_playwright

class BaseScraper(ABC):
    def __init__(self):
        self.headers = {'User-Agent': USER_AGENT}

    @abstractmethod
    def fetch_holdings(self):
        """Fetch holdings and return a standardized DataFrame."""
        pass

    def clean_dataframe(self, df):
        """Standardize the DataFrame columns."""
        # Ensure numeric columns are actually numeric
        numeric_cols = ['shares', 'market_value', 'weight', 'strike_price']
        for col in numeric_cols:
            if col in df.columns:
                # Remove currency symbols and commas
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.replace(r'[$,%]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df

    def _extract_option_details(self, df):
        """
        Generic option extractor handling multiple formats:
        1. NEOS: 'NDX US 12/20/24 C26150'
        2. GPIQ: 'C/QQQ ... 610.3 EXP 2026-03-06'
        3. Roundhill: '4NDX 260320C01947250'
        """
        if 'asset_class' not in df.columns:
            df['asset_class'] = 'Equity'
        
        # Ensure target columns exist
        for col in ['strike_price', 'expiration_date', 'option_type']:
            if col not in df.columns:
                df[col] = None

        def parse_row(row):
            ticker = str(row.get('holding_ticker', ''))
            desc = str(row.get('description', ''))
            text = f"{ticker} {desc}"

            # 1. NEOS / Standard (MM/DD/YY [CP]Strike)
            # e.g. "NDX US 12/20/24 C26150"
            m1 = re.search(r'(\d{2}/\d{2}/\d{2})\s+([CP])(\d+)', text)
            if m1:
                return {
                    'asset_class': 'Option',
                    'option_type': 'Call' if m1.group(2).upper() == 'C' else 'Put',
                    'strike_price': float(m1.group(3)),
                    'expiration_date': m1.group(1)
                }

            # 2. GPIQ / GS (Type/Underlying ... Strike EXP YYYY-MM-DD)
            # e.g. "C/QQQ FLEX ... 610.3 EXP 2026-03-06"
            m2 = re.search(r'(C|P)/([A-Z]+)\s+.*?\s+([\d\.]+)\s+EXP\s+(\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
            if m2:
                return {
                    'asset_class': 'Option',
                    'option_type': 'Call' if m2.group(1).upper() == 'C' else 'Put',
                    'strike_price': float(m2.group(3)),
                    'expiration_date': m2.group(4)
                }

            # 3. Roundhill / OCC Format (YYMMDD[CP]StrikeDigits)
            # e.g. "4NDX 260320C01947250"
            # Strike is last 8 digits, usually 3 decimals
            m3 = re.search(r'(\d{6})([CP])(\d{8})', ticker.replace(' ', ''))
            if m3:
                yymmdd = m3.group(1)
                opt_type = m3.group(2).upper()
                strike_raw = m3.group(3)
                strike = float(strike_raw) / 100.0
                
                # Format YYMMDD to YYYY-MM-DD
                exp_date = f"20{yymmdd[:2]}-{yymmdd[2:4]}-{yymmdd[4:]}"
                
                return {
                    'asset_class': 'Option',
                    'option_type': 'Call' if opt_type == 'C' else 'Put',
                    'strike_price': strike,
                    'expiration_date': exp_date
                }
            
            return None

        for idx, row in df.iterrows():
            res = parse_row(row)
            if res:
                df.at[idx, 'asset_class'] = res['asset_class']
                df.at[idx, 'option_type'] = res['option_type']
                df.at[idx, 'strike_price'] = res['strike_price']
                df.at[idx, 'expiration_date'] = res['expiration_date']
        
        # Debug print
        opt_count = df[df['asset_class'] == 'Option'].shape[0]
        if opt_count > 0:
            print(f"Extracted {opt_count} options.")

class QQQIScraper(BaseScraper):
    def fetch_holdings(self):
        print("Fetching QQQI holdings...")
        # Add headers to mimic browser AJAX request
        headers = self.headers.copy()
        headers.update({
            'Referer': 'https://neosfunds.com/qqqi/',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://neosfunds.com'
        })
        
        params = {
            'action': 'download_holdings_csv',
            'ticker': 'QQQI'
        }
        try:
            response = requests.get(QQQI_AJAX_URL, headers=headers, params=params)
            response.raise_for_status()
            
            content = response.content.decode('utf-8-sig')

            if content.strip().startswith("<!DOCTYPE") or content.strip().startswith("<html"):
                 print("QQQI returned HTML:", content[:200])
                 return pd.DataFrame()

            column_names = [
                'date', 'etf_ticker', 'holding_ticker', 'cusip', 'description', 
                'shares', 'price', 'market_value', 'weight', 'net_assets', 'total_shares', 'cash_component', 'dummy'
            ]
            
            # Note: The CSV from QQQI has a trailing comma, so 'dummy' column catches the empty field
            df = pd.read_csv(io.StringIO(content), names=column_names, header=None)
            
            # Drop the header row if it exists (it starts with "Date")
            # Also filter out any non-data rows
            df = df[df['date'].astype(str).str.lower() != 'date']
            
            # Clean formatted strings
            cols_to_clean = ['shares', 'market_value', 'weight', 'price']
            for col in cols_to_clean:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(r'[$,%]', '', regex=True)
            
            # Clean Weight (percentage to decimal)
            df['weight'] = pd.to_numeric(df['weight'], errors='coerce') / 100.0
            
            df['asset_class'] = 'Equity' 
            
            self._extract_option_details(df)
            
            return self.clean_dataframe(df)
            
        except Exception as e:
            print(f"Error fetching QQQI: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


class GPIQScraper(BaseScraper):
    def fetch_holdings(self):
        print("Fetching GPIQ holdings using Playwright...")
        try:
             with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                # Use a realistic user agent
                context = browser.new_context(user_agent=self.headers['User-Agent'])
                page = context.new_page()
                
                print(f"Navigating to GPIQ Page: {GPIQ_HOLDINGS_URL}")
                try:
                    # Use domcontentloaded which is faster and sufficient for elements to exist
                    page.goto(GPIQ_HOLDINGS_URL, wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    print(f"Playwright navigation warning (proceeding): {e}")
                    # Proceed anyway, sometimes it times out but page is usable
                
                # Wait for dynamic content
                print("Waiting 5s for page content load...", flush=True)
                time.sleep(5)

                # Handle possible modal
                print("Checking for GPIQ modals...", flush=True)
                try:
                    modal_active = False
                    modal_buttons = page.locator(".gs-modal__wrapper button, .gs-modal button")
                    cnt = modal_buttons.count()
                    
                    if cnt > 0:
                        for i in range(cnt):
                            btn_text = modal_buttons.nth(i).inner_text()
                            # Do NOT click "Change" - it's likely a settings button, not a modal close
                            if "individual" in btn_text.lower() or "agree" in btn_text.lower() or "accept" in btn_text.lower() or "continue" in btn_text.lower():
                                print(f"Clicking modal button: {btn_text}")
                                modal_buttons.nth(i).click()
                                time.sleep(2)
                                modal_active = True
                                break
                    
                    if not modal_active:
                         print("No blocking modal action taken. Relying on JS click bypass.")
                             
                except Exception as e:
                    print(f"Error checking modals: {e}")

                # Find Download Button
                print("Looking for download button...", flush=True)
                # XPath for "All Holdings" and "download"
                download_btn = page.locator("//button[contains(normalize-space(.), 'All Holdings') and contains(normalize-space(.), 'download')]")
                
                count = download_btn.count()
                
                if count > 0:
                    print("Found 'All Holdings' button. Clicking via JS...")
                    with page.expect_download(timeout=30000) as download_info:
                        # Use JS click to bypass overlays
                        download_btn.first.evaluate("el => el.click()")
                    
                    download = download_info.value
                    # Save to a stable path to avoid deletion
                    temp_path = os.path.join(os.getcwd(), "gpiq_holdings_temp.xlsx")
                    download.save_as(temp_path)
                    print(f"Downloaded GPIQ to {temp_path}")
                    
                    # Read Excel
                    df = pd.read_excel(temp_path)
                    
                    # Clean columns
                    # Find header row
                    header_idx = None
                    for i, row in df.head(10).iterrows():
                        row_str = row.astype(str).str.lower()
                        if row_str.str.contains('ticker').any():
                            header_idx = i
                            break
                    
                    if header_idx is not None:
                         # i is index in df (which started at row 1 of excel)
                         # so header is at excel row i + 1
                         df = pd.read_excel(temp_path, header=header_idx + 1)
                    
                    browser.close()
                    
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    df.columns = df.columns.str.strip()
                    
                    column_map = {
                        'Ticker': 'holding_ticker',
                        'Description': 'description',
                        'Security Name': 'description',
                        'Shares': 'shares',
                        'Market Value': 'market_value',
                        'Weight (%)': 'weight',
                        'Weight': 'weight',
                        'Asset Class': 'asset_class'
                    }
                    df = df.rename(columns=column_map)
                    
                    if 'weight' in df.columns:
                        df['weight'] = pd.to_numeric(df['weight'], errors='coerce') / 100.0
                    
                    self._extract_option_details(df)
                    return self.clean_dataframe(df)

                else:
                    print("GPIQ: 'All Holdings' download button not found.")
                    browser.close()
                    return pd.DataFrame()

        except Exception as e:
            print(f"Error fetching GPIQ: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()


class QYLDScraper(BaseScraper):
    def fetch_holdings(self):
        print("Fetching QYLD holdings...")
        # URL pattern: https://assets.globalxetfs.com/funds/holdings/qyld_full-holdings_{date}.csv
        # date format: YYYYMMDD
        date_str = datetime.now().strftime('%Y%m%d')
        url = QYLD_HOLDINGS_URL_BASE.format(date=date_str)
        
        try:
            print(f"Attempting QYLD URL: {url}")
            response = requests.get(url, headers=self.headers)
            
            # If 404, maybe try yesterday?
            if response.status_code == 404:
                print("Today's file not found. Trying yesterday...")
                from datetime import timedelta
                yesterday = datetime.now() - timedelta(days=1)
                date_str = yesterday.strftime('%Y%m%d')
                url = QYLD_HOLDINGS_URL_BASE.format(date=date_str)
                print(f"Attempting QYLD URL: {url}")
                response = requests.get(url, headers=self.headers)

            response.raise_for_status()
            
            # Identify header row by scanning text first to avoid initial read_csv error
            content_str = response.content.decode('utf-8')
            lines = content_str.splitlines()
            header_idx = None
            
            for i, line in enumerate(lines[:20]):
                if 'Ticker' in line and 'Name' in line:
                    header_idx = i
                    break
            
            if header_idx is not None:
                df = pd.read_csv(io.StringIO(content_str), header=header_idx)
            else:
                # If header not found, try reading directly (maybe it's clean?)
                df = pd.read_csv(io.StringIO(content_str))
            
            # Clean columns
            df.columns = df.columns.str.strip()
            
            column_map = {
                'Ticker': 'holding_ticker',
                'Name': 'description',
                'Market Value ($)': 'market_value',
                'Shares Held': 'shares',
                '% of Net Assets': 'weight'
            }
            df = df.rename(columns=column_map)
            
            if 'weight' in df.columns:
                df['weight'] = pd.to_numeric(df['weight'], errors='coerce') / 100.0
            
            # Add asset class
            df['asset_class'] = df['holding_ticker'].apply(lambda x: 'Cash' if 'Cash' in str(x) else 'Equity')
            
            # Extract options
            self._extract_option_details(df)
            
            return self.clean_dataframe(df)

        except Exception as e:
            print(f"Error fetching QYLD: {e}")
            return pd.DataFrame()


class QDTEScraper(BaseScraper):
    def fetch_holdings(self):
        print("Fetching QDTE holdings using Playwright...")
        try:
             with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.headers['User-Agent'])
                
                print(f"Navigating to {QDTE_HOLDINGS_URL}")
                page.goto(QDTE_HOLDINGS_URL, wait_until="networkidle", timeout=60000)
                
                # Click the CSV link
                # It has id="csvlink"
                csv_link = page.locator("#csvlink")
                if csv_link.count() > 0:
                    print("Found QDTE CSV Link. Clicking...")
                    with page.expect_download() as download_info:
                        csv_link.click()
                    download = download_info.value
                    
                    save_path = download.path()
                    print(f"Downloaded QDTE CSV to {save_path}")
                    
                    df = pd.read_csv(save_path)
                    
                    column_map = {
                        'Ticker': 'holding_ticker',
                        'Name': 'description',
                        'Market Value': 'market_value',
                        'Shares': 'shares',
                        'Weight': 'weight'
                    }
                    df = df.rename(columns=column_map)
                    
                    # Weight: 4.37% -> 0.0437
                    if 'weight' in df.columns:
                        df['weight'] = df['weight'].astype(str).str.replace('%', '').astype(float) / 100.0
                    
                    browser.close()
                    
                    self._extract_option_details(df)
                    return self.clean_dataframe(df)
                    
                else:
                    print("QDTE CSV Link #csvlink not found.")
                    browser.close()
                    return pd.DataFrame()
                    
        except Exception as e:
            print(f"Error fetching QDTE: {e}")
            return pd.DataFrame()
