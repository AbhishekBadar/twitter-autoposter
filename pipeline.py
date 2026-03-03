"""Standalone pipeline script for GitHub Actions: research → generate → sheet → telegram."""

import logging
import sys
import requests
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from researcher import research_all
from generator import generate_all_posts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pipeline")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_telegram(text, reply_markup=None):
    """Send a message via Telegram Bot API."""
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        import json
        payload["reply_markup"] = json.dumps(reply_markup)

    resp = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def write_post_to_sheet(post, row_num):
    """Write a single post to Google Sheet."""
    import gspread
    from google.oauth2.service_account import Credentials
    from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    # Ensure Posts Queue sheet exists
    try:
        sheet = spreadsheet.worksheet("Posts Queue")
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title="Posts Queue", rows=1000, cols=8)

    headers = ["ID", "Content", "Format", "Characters", "Source", "Status", "Date Added", "Notes"]
    if not sheet.row_values(1):
        sheet.update("A1:H1", [headers])
        sheet.format("A1:H1", {"textFormat": {"bold": True}})

    content = post["content"]
    row_data = [
        row_num,
        content,
        post["format"],
        len(content),
        post.get("source_topic", ""),
        "Pending Review",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "",
    ]
    sheet.append_row(row_data, value_input_option="USER_ENTERED")

    # Return actual row number
    all_values = sheet.get_all_values()
    return len(all_values)


def main():
    logger.info("=" * 50)
    logger.info("Pipeline started at %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 50)

    # Step 1: Research
    logger.info("Step 1: Researching trending content...")
    try:
        topics = research_all()
        if not topics:
            logger.warning("No topics found")
            send_telegram("⚠️ Pipeline: No topics found from any source.")
            return
        logger.info("Found %d topics", len(topics))
    except Exception as e:
        logger.error("Research failed: %s", e)
        send_telegram(f"❌ Pipeline failed at research: {e}")
        return

    # Step 2: Generate posts
    logger.info("Step 2: Generating posts with DeepSeek...")
    try:
        posts = generate_all_posts(topics[:20])
        if not posts:
            logger.warning("No posts generated")
            send_telegram("⚠️ Pipeline: DeepSeek generated no posts.")
            return
        logger.info("Generated %d posts", len(posts))
    except Exception as e:
        logger.error("Generation failed: %s", e)
        send_telegram(f"❌ Pipeline failed at generation: {e}")
        return

    # Step 3: Write to sheet and send to Telegram
    logger.info("Step 3: Writing to sheet and sending to Telegram...")
    send_telegram(f"🔔 <b>{len(posts)} new posts generated!</b>\nReview each one below:")

    for i, post in enumerate(posts, 1):
        try:
            # Write to Google Sheet first
            sheet_row = write_post_to_sheet(post, i)
            logger.info("Post %d written to sheet row %d", i, sheet_row)

            # Send to Telegram with buttons
            content = post["content"]
            chars = len(content)
            fmt = post["format"]
            separator = "─" * 30

            msg_text = (
                f"📝 <b>{fmt}</b> | {chars} chars | Row: {sheet_row}\n"
                f"{separator}\n\n"
                f"{content}"
            )

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Approve", "callback_data": f"approve_{sheet_row}"},
                        {"text": "❌ Reject", "callback_data": f"reject_{sheet_row}"},
                    ]
                ]
            }

            result = send_telegram(msg_text, reply_markup=keyboard)
            logger.info("Post %d sent to Telegram (msg_id: %s)", i, result["result"]["message_id"])

        except Exception as e:
            logger.error("Failed to process post %d: %s", i, e)

    logger.info("Pipeline complete — awaiting approval in Telegram")


if __name__ == "__main__":
    main()
