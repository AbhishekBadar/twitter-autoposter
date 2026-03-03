# X-Autoposter

Automated X (Twitter) content pipeline that researches viral content daily, generates posts using DeepSeek AI, sends them via Telegram for approval, and writes approved posts to Google Sheets.

## Flow

```
Research trending content → DeepSeek generates 3 posts → Telegram approval (✅/❌/✏️) → Google Sheet
```

## Post Formats (3 per day)

1. **VIRAL_FACT** — Shocking stat or fact, punchy caption (< 280 chars)
2. **NEWS_REACTION** — Top story + sharp take (< 280 chars)
3. **THREAD** — 5-tweet deep dive on the most interesting story

## Data Sources

- HackerNews top stories
- Reddit (r/nextfuckinglevel, r/worldnews, r/interestingasfuck, r/todayilearned, r/technology, r/artificial)
- Google Trends (US trending searches)
- RSS feeds (TechCrunch, BBC News, The Verge, VentureBeat)
- ArXiv AI papers (cs.AI)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 3. Get your Telegram Chat ID

1. Message [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your Chat ID

### 4. Create a Google Cloud service account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **IAM & Admin → Service Accounts**
5. Create a service account and download the JSON key file
6. Create a Google Sheet and share it with the service account email (the email ending in `@*.iam.gserviceaccount.com`)
7. Copy the Sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`

### 5. Get a DeepSeek API key

1. Go to [platform.deepseek.com](https://platform.deepseek.com)
2. Create an account and generate an API key

### 6. Configure environment

```bash
cp .env.example .env
```

Fill in all values in `.env`:

```
DEEPSEEK_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=your-chat-id
GOOGLE_SHEET_ID=your-sheet-id
GOOGLE_CREDENTIALS_FILE=credentials.json
```

### 7. Test

```bash
# Run the full pipeline once immediately
python main.py --now

# Or test just the research step
python main.py --research
```

## Usage

```bash
# Production: start scheduler + Telegram bot
python main.py

# Run pipeline once immediately (testing)
python main.py --now

# Print recent posts status
python main.py --status

# Run only research step
python main.py --research
```

## Telegram Commands

- **Inline buttons** on each post: ✅ Approve | ❌ Reject | ✏️ Edit
- **Edit flow**: Reply with `EDIT_<id>: <new content>`
- **/status**: View today's stats and recent posts

## Google Sheet Structure

**Posts Queue** sheet:
| ID | Content | Format | Characters | Source | Status | Date Added | Notes |

**Analytics** sheet:
| Date | Posts Generated | Posts Approved | Posts Rejected |

## Project Structure

```
├── main.py              # Orchestrator + APScheduler + CLI
├── researcher.py        # Fetches trending content from all sources
├── generator.py         # DeepSeek API generates posts
├── telegram_bot.py      # Approval flow with inline buttons
├── sheets.py            # Google Sheets integration
├── database.py          # SQLite queue and status tracking
├── config.py            # Settings loaded from .env
├── .env.example         # API key template
├── requirements.txt     # Python dependencies
└── README.md
```
