import pandas as pd
from playwright.sync_api import sync_playwright
import io
import os
from jinja2 import Template

class TableVisualizer:
    TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            
            body {
                font-family: 'Roboto', sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #ffffff;
                width: fit-content;
            }
            
            table {
                border-collapse: collapse;
                width: 100%;
                min-width: 800px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            
            th {
                text-align: left;
                padding: 12px 16px;
                background-color: #f8f9fa;
                color: #5f6368;
                font-weight: 500;
                font-size: 13px;
                border-bottom: 2px solid #e0e0e0;
            }
            
            td {
                padding: 12px 16px;
                border-bottom: 1px solid #f0f0f0;
                color: #202124;
                font-size: 14px;
            }
            
            tr:hover {
                background-color: #f8f9fa;
            }
            
            .stock-cell {
                font-weight: 500;
                color: #1a73e8;
            }
            
            .etf-cell {
                font-weight: 700;
                color: #202124;
                background-color: #f1f3f4;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }
            
            .sector-cell {
                color: #5f6368;
                font-size: 12px;
                text-transform: uppercase;
            }
            
            .positive {
                color: #137333;
                background-color: #e6f4ea;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 500;
                display: inline-block;
            }
            
            .negative {
                color: #c5221f;
                background-color: #fce8e6;
                padding: 4px 8px;
                border-radius: 4px;
                font-weight: 500;
                display: inline-block;
            }
            
            .numeric {
                text-align: right;
                font-family: 'Roboto Mono', monospace;
            }
            
            .header-row {
                display: flex;
                align-items: center;
                margin-bottom: 15px;
            }
            
            .header-title {
                font-size: 20px;
                font-weight: 700;
                color: #202124;
            }
            
            .header-date {
                margin-left: auto;
                color: #5f6368;
            }
        </style>
    </head>
    <body>
        <div class="header-row">
            <div class="header-title">{{ title }}</div>
            <div class="header-date">{{ date }}</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ETF</th>
                    <th>Symbol</th>
                    <th>Description</th>
                    <th class="numeric">Shares</th>
                    <th class="numeric">Market Value</th>
                    <th class="numeric">Weight</th>
                    <th class="numeric">Change</th>
                    <th class="numeric">% Change</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td class="stock-cell">{{ row.holding_ticker }}</td>
                    <td class="sector-cell">{{ row.description }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares) }}</td>
                    <td class="numeric">${{ "{:,.2f}".format(row.market_value) }}</td>
                    <td class="numeric">{{ "{:.2f}%".format(row.weight * 100) }}</td>
                    <td class="numeric">
                        {% if row.shares_change > 0 %}
                            <span class="positive">↑ {{ "{:,.0f}".format(row.shares_change) }}</span>
                        {% elif row.shares_change < 0 %}
                            <span class="negative">↓ {{ "{:,.0f}".format(row.shares_change|abs) }}</span>
                        {% else %}
                            <span style="color: #9aa0a6">-</span>
                        {% endif %}
                    </td>
                    <td class="numeric">
                        {% if row.pct_change > 0 %}
                            <span class="positive">+{{ "{:.2f}%".format(row.pct_change) }}</span>
                        {% elif row.pct_change < 0 %}
                            <span class="negative">{{ "{:.2f}%".format(row.pct_change) }}</span>
                        {% else %}
                            <span style="color: #9aa0a6">-</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """

    OPTIONS_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500&display=swap');
            
            body { font-family: 'Roboto', sans-serif; margin: 0; padding: 20px; background-color: #ffffff; width: fit-content; }
            table { border-collapse: collapse; width: 100%; min-width: 800px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            th { text-align: left; padding: 12px 16px; background-color: #f8f9fa; color: #5f6368; font-weight: 500; font-size: 13px; border-bottom: 2px solid #e0e0e0; }
            td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; color: #202124; font-size: 14px; }
            tr:hover { background-color: #f8f9fa; }
            .header-row { display: flex; align-items: center; margin-bottom: 15px; }
            .header-title { font-size: 20px; font-weight: 700; color: #202124; }
            .header-date { margin-left: auto; color: #5f6368; }
            .numeric { text-align: right; font-family: 'Roboto Mono', monospace; }
            .option-type-call { color: #137333; font-weight: 500; }
            .option-type-put { color: #c5221f; font-weight: 500; }
            .etf-cell { font-weight: 700; color: #202124; background-color: #f1f3f4; border-radius: 4px; padding: 4px 8px; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="header-row">
            <div class="header-title">{{ title }}</div>
            <div class="header-date">{{ date }}</div>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ETF</th>
                    <th>Ticker</th>
                    <th>Type</th>
                    <th class="numeric">Strike</th>
                    <th>Expiration</th>
                    <th class="numeric">Shares/Val</th>
                    <th class="numeric">Weight</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td>{{ row.holding_ticker }}</td>
                    <td class="{{ 'option-type-call' if row.option_type == 'Call' else 'option-type-put' }}">{{ row.option_type }}</td>
                    <td class="numeric">{{ "{:,.2f}".format(row.strike_price) }}</td>
                    <td>{{ row.expiration_date }}</td>
                    <td class="numeric">
                        {% if row.market_value and row.market_value > 0 %}
                             ${{ "{:,.2f}".format(row.market_value) }}
                        {% else %}
                             {{ "{:,.0f}".format(row.shares) }}
                        {% endif %}
                    </td>
                    <td class="numeric">{{ "{:.2f}%".format(row.weight * 100) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """

    CHANGES_TEMPLATE = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap');
            body { font-family: 'Roboto', sans-serif; margin: 0; padding: 20px; background-color: #ffffff; width: fit-content; }
            .section-title { font-size: 16px; font-weight: 700; color: #202124; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }
            .header-row { display: flex; align-items: center; margin-bottom: 15px; }
            .header-title { font-size: 20px; font-weight: 700; color: #202124; }
            .header-date { margin-left: auto; color: #5f6368; }
            table { border-collapse: collapse; width: 100%; min-width: 600px; margin-bottom: 20px; }
            th { text-align: left; padding: 8px 12px; background-color: #f1f3f4; color: #5f6368; font-size: 12px; }
            td { padding: 8px 12px; border-bottom: 1px solid #f0f0f0; font-size: 13px; }
            .numeric { text-align: right; font-family: 'Roboto Mono', monospace; }
            .badge-new { background-color: #e6f4ea; color: #137333; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
            .badge-sold { background-color: #fce8e6; color: #c5221f; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
            .badge-inc { background-color: #e8f0fe; color: #1967d2; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
            .badge-dec { background-color: #fef7e0; color: #ea8600; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
            .etf-cell { font-weight: 700; color: #202124; background-color: #f1f3f4; border-radius: 4px; padding: 2px 6px; font-size: 11px; margin-right: 5px; }
            .empty-msg { color: #5f6368; font-style: italic; font-size: 13px; }
        </style>
    </head>
    <body>
        <div class="header-row">
            <div class="header-title">{{ title }}</div>
            <div class="header-date">{{ date }}</div>
        </div>

        <div class="section-title">New Positions ({{ new|length }})</div>
        {% if new %}
        <table>
            <thead><tr><th>ETF</th><th>Ticker</th><th>Description</th><th class="numeric">Shares</th><th class="numeric">Weight</th></tr></thead>
            <tbody>
                {% for row in new %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td><span class="badge-new">NEW</span> {{ row.holding_ticker }}</td>
                    <td>{{ row.description }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares) }}</td>
                    <td class="numeric">{{ "{:.2f}%".format(row.weight * 100) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}<div class="empty-msg">No new positions.</div>{% endif %}

        <div class="section-title">Sold Positions ({{ sold|length }})</div>
        {% if sold %}
        <table>
            <thead><tr><th>ETF</th><th>Ticker</th><th>Description</th><th class="numeric">Shares</th></tr></thead>
            <tbody>
                {% for row in sold %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td><span class="badge-sold">SOLD</span> {{ row.holding_ticker }}</td>
                    <td>{{ row.description }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}<div class="empty-msg">No sold positions.</div>{% endif %}
        
        <div class="section-title">Increased Positions ({{ increased|length }})</div>
        {% if increased %}
        <table>
            <thead><tr><th>ETF</th><th>Ticker</th><th class="numeric">Shares Today</th><th class="numeric">Change</th></tr></thead>
            <tbody>
                {% for row in increased %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td><span class="badge-inc">INC</span> {{ row.holding_ticker }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares_today) }}</td>
                    <td class="numeric">+{{ "{:,.0f}".format(row.shares_change) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}<div class="empty-msg">No increased positions.</div>{% endif %}

        <div class="section-title">Decreased Positions ({{ decreased|length }})</div>
        {% if decreased %}
        <table>
            <thead><tr><th>ETF</th><th>Ticker</th><th class="numeric">Shares Today</th><th class="numeric">Change</th></tr></thead>
            <tbody>
                {% for row in decreased %}
                <tr>
                    <td><span class="etf-cell">{{ row.etf_ticker }}</span></td>
                    <td><span class="badge-dec">DEC</span> {{ row.holding_ticker }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares_today) }}</td>
                    <td class="numeric">{{ "{:,.0f}".format(row.shares_change) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}<div class="empty-msg">No decreased positions.</div>{% endif %}
    </body>
    </html>
    """

    @staticmethod
    def _render_and_screenshot(html_content):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content)
            body = page.locator("body")
            image_bytes = body.screenshot()
            browser.close()
            return image_bytes

    @staticmethod
    def generate_image(df, title="Holdings Report", date_str=""):
        # ... existing implementation refactored to use _render_and_screenshot ...
        if 'shares_change' not in df.columns:
            df['shares_change'] = 0
            
        df = df.copy()
        df['prev_shares'] = df['shares'] - df['shares_change']
        
        def calc_pct(row):
            if row['prev_shares'] == 0:
                return 100.0 if row['shares'] > 0 else 0.0
            return (row['shares_change'] / row['prev_shares']) * 100.0
            
        df['pct_change'] = df.apply(calc_pct, axis=1)
        
        if 'weight' in df.columns:
            df = df.sort_values('weight', ascending=False)
            
        # Fill NaNs to avoid Jinja formatting errors
        df = df.fillna(0)
        
        rows = df.to_dict('records')
        template = Template(TableVisualizer.TEMPLATE)
        html_content = template.render(title=title, date=date_str, rows=rows)
        
        return TableVisualizer._render_and_screenshot(html_content)

    @staticmethod
    def generate_options_image(df, title="Options Report", date_str=""):
        # Filter for options if not already done, or assume caller passes options df
        if 'asset_class' in df.columns:
            df = df[df['asset_class'] == 'Option'].copy()
        
        if df.empty:
            return None

        # Ensure cols
        for col in ['strike_price', 'market_value', 'weight', 'shares']:
             if col not in df.columns: df[col] = 0

        # Fill NaNs
        df = df.fillna(0)

        # Sort by Expiration then Strike
        if 'expiration_date' in df.columns and 'strike_price' in df.columns:
            df = df.sort_values(['expiration_date', 'strike_price'])
            
        rows = df.to_dict('records')
        template = Template(TableVisualizer.OPTIONS_TEMPLATE)
        html_content = template.render(title=title, date=date_str, rows=rows)
        
        return TableVisualizer._render_and_screenshot(html_content)

    @staticmethod
    def generate_changes_image(diffs, title="Changes Report", date_str=""):
        # diffs is the dict from compare_holdings
        # keys: new, sold, increased, decreased
        
        # Helper to sanitize list of dicts
        def sanitize(df):
            if df.empty: return []
            return df.fillna(0).to_dict('records')

        new_rows = sanitize(diffs['new'])
        sold_rows = sanitize(diffs['sold'])
        inc_rows = sanitize(diffs['increased'])
        dec_rows = sanitize(diffs['decreased'])
        
        template = Template(TableVisualizer.CHANGES_TEMPLATE)
        html_content = template.render(title=title, date=date_str, 
                                     new=new_rows, sold=sold_rows, 
                                     increased=inc_rows, decreased=dec_rows)
        
        return TableVisualizer._render_and_screenshot(html_content)

def main():
    # Test stub
    data = [
        {'holding_ticker': 'AAPL', 'description': 'Apple Inc.', 'shares': 150000, 'market_value': 25000000, 'weight': 0.05, 'shares_change': -5000},
        {'holding_ticker': 'NVDA', 'description': 'NVIDIA Corp', 'shares': 20000, 'market_value': 18000000, 'weight': 0.04, 'shares_change': 1000},
        {'holding_ticker': 'MSFT', 'description': 'Microsoft', 'shares': 100000, 'market_value': 40000000, 'weight': 0.08, 'shares_change': 0},
    ]
    df = pd.DataFrame(data)
    img = TableVisualizer.generate_image(df, title="Test Report", date_str="2024-02-19")
    with open("test_table.png", "wb") as f:
        f.write(img)
    print("Generated test_table.png")

if __name__ == "__main__":
    main()
