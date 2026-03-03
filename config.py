"""Configuration loaded from .env file."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


# DeepSeek API
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Google Sheets
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

# Scheduling
SCHEDULE_HOUR = int(os.getenv("SCHEDULE_HOUR", "7"))
SCHEDULE_MINUTE = int(os.getenv("SCHEDULE_MINUTE", "0"))

# Database
DB_PATH = Path(__file__).parent / "x_autoposter.db"

# Logging
LOG_FILE = Path(__file__).parent / "errors.log"

# Reddit RSS subreddits
REDDIT_SUBREDDITS = [
    "nextfuckinglevel",
    "worldnews",
    "interestingasfuck",
    "todayilearned",
    "technology",
    "artificial",
]

# RSS feeds
RSS_FEEDS = {
    "TechCrunch": "https://techcrunch.com/feed/",
    "BBC News": "http://feeds.bbci.co.uk/news/rss.xml",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "VentureBeat": "https://venturebeat.com/feed/",
    "ArXiv AI": "https://rss.arxiv.org/rss/cs.AI",
}

# Post formats
POST_FORMATS = ["VIRAL_FACT", "NEWS_REACTION", "THREAD"]

# Validation
REQUIRED_VARS = [
    ("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY),
    ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
    ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
    ("GOOGLE_SHEET_ID", GOOGLE_SHEET_ID),
]


def validate_config():
    """Return list of missing required config variables."""
    return [name for name, value in REQUIRED_VARS if not value]
