import os

# Base Directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database
DB_NAME = "etf_data.db"
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

# User Agent
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

# URLs
QQQI_AJAX_URL = "https://neosfunds.com/wp-admin/admin-ajax.php"
GPIQ_HOLDINGS_URL = "https://am.gs.com/en-us/individual/funds/detail/PV105259/38149W630/goldman-sachs-nasdaq-100-premium-income-etf"

# New ETFs
QYLD_HOLDINGS_URL_BASE = "https://assets.globalxetfs.com/funds/holdings/qyld_full-holdings_{date}.csv"
QDTE_HOLDINGS_URL = "https://www.roundhillinvestments.com/etf/qdte"

# ETF Configs
ETFS = {
    "QQQI": {
        "name": "NEOS Nasdaq 100(R) High Income ETF",
        "scraper_class": "QQQIScraper"
    },
    "GPIQ": {
        "name": "Goldman Sachs Nasdaq-100 Premium Income ETF",
        "scraper_class": "GPIQScraper"
    },
    "QYLD": {
        "name": "Global X Nasdaq 100 Covered Call ETF",
        "scraper_class": "QYLDScraper"
    },
    "QDTE": {
        "name": "Roundhill N-100 0DTE Covered Call Strategy ETF",
        "scraper_class": "QDTEScraper"
    }
}
