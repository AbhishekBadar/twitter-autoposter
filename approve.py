"""Process Telegram button callbacks and update Google Sheet accordingly."""

import logging
import sys
import json
import requests
from datetime import datetime

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("approve")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
OFFSET_FILE = "/tmp/telegram_offset.txt"


def get_sheet():
    """Get the Posts Queue worksheet."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return spreadsheet.worksheet("Posts Queue")


def update_sheet_status(sheet_row, status):
    """Update the Status column (column 6) for a given row."""
    sheet = get_sheet()
    sheet.update_cell(sheet_row, 6, status)

    # Green background for approved, red for rejected
    if status == "Ready to Post":
        sheet.format(f"A{sheet_row}:H{sheet_row}", {
            "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}
        })
    elif status == "Rejected":
        sheet.format(f"A{sheet_row}:H{sheet_row}", {
            "backgroundColor": {"red": 0.95, "green": 0.85, "blue": 0.85}
        })

    logger.info("Sheet row %d updated to '%s'", sheet_row, status)


def update_analytics(approved, rejected, total):
    """Add a row to the Analytics sheet."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        GOOGLE_CREDENTIALS_FILE,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)

    try:
        analytics = spreadsheet.worksheet("Analytics")
    except Exception:
        analytics = spreadsheet.add_worksheet(title="Analytics", rows=1000, cols=4)

    headers = ["Date", "Posts Generated", "Posts Approved", "Posts Rejected"]
    if not analytics.row_values(1):
        analytics.update("A1:D1", [headers])
        analytics.format("A1:D1", {"textFormat": {"bold": True}})

    today = datetime.now().strftime("%Y-%m-%d")
    analytics.append_row([today, total, approved, rejected], value_input_option="USER_ENTERED")
    logger.info("Analytics updated: %d approved, %d rejected out of %d", approved, rejected, total)


def answer_callback(callback_query_id, text):
    """Answer a Telegram callback query."""
    requests.post(
        f"{TELEGRAM_API}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )


def edit_message(chat_id, message_id, text):
    """Edit a Telegram message (removes buttons)."""
    requests.post(
        f"{TELEGRAM_API}/editMessageText",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=10,
    )


def send_message(text):
    """Send a Telegram message."""
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
        timeout=10,
    )


def main():
    logger.info("Checking for Telegram approvals...")

    # Get updates from Telegram
    params = {"timeout": 5, "allowed_updates": ["callback_query"]}

    # Use offset to avoid processing old callbacks
    try:
        with open(OFFSET_FILE, "r") as f:
            params["offset"] = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        pass

    resp = requests.get(f"{TELEGRAM_API}/getUpdates", params=params, timeout=15)
    resp.raise_for_status()
    updates = resp.json().get("result", [])

    if not updates:
        logger.info("No pending approvals found")
        return

    logger.info("Found %d updates to process", len(updates))

    approved_count = 0
    rejected_count = 0
    total_count = 0

    for update in updates:
        callback = update.get("callback_query")
        if not callback:
            continue

        # Verify it's from the authorized chat
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        if str(chat_id) != str(TELEGRAM_CHAT_ID):
            continue

        data = callback.get("data", "")
        callback_id = callback["id"]
        message_id = callback["message"]["message_id"]
        original_text = callback["message"].get("text", "")

        try:
            action, sheet_row_str = data.split("_", 1)
            sheet_row = int(sheet_row_str)
        except (ValueError, IndexError):
            logger.warning("Invalid callback data: %s", data)
            answer_callback(callback_id, "Invalid action")
            continue

        total_count += 1

        if action == "approve":
            update_sheet_status(sheet_row, "Ready to Post")
            answer_callback(callback_id, "✅ Approved!")
            # Extract just the post content from the message
            lines = original_text.split("\n")
            content_start = next((i for i, l in enumerate(lines) if l.startswith("─")), 1) + 1
            content = "\n".join(lines[content_start:]).strip()
            edit_message(chat_id, message_id, f"✅ APPROVED\n\n{content}")
            approved_count += 1
            logger.info("Row %d approved", sheet_row)

        elif action == "reject":
            update_sheet_status(sheet_row, "Rejected")
            answer_callback(callback_id, "❌ Rejected")
            lines = original_text.split("\n")
            content_start = next((i for i, l in enumerate(lines) if l.startswith("─")), 1) + 1
            content = "\n".join(lines[content_start:]).strip()
            edit_message(chat_id, message_id, f"❌ REJECTED\n\n{content}")
            rejected_count += 1
            logger.info("Row %d rejected", sheet_row)

    # Save offset so we don't reprocess
    if updates:
        new_offset = updates[-1]["update_id"] + 1
        with open(OFFSET_FILE, "w") as f:
            f.write(str(new_offset))

    # Send summary if any actions were processed
    if total_count > 0:
        summary = (
            f"📊 <b>Approvals Processed!</b>\n"
            f"✅ Approved: {approved_count}\n"
            f"❌ Rejected: {rejected_count}\n"
            f"Sheet updated."
        )
        send_message(summary)
        update_analytics(approved_count, rejected_count, total_count)

    logger.info("Done — processed %d actions", total_count)


if __name__ == "__main__":
    main()
