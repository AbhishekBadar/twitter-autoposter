"""Google Sheets integration for storing approved posts."""

import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE
import database as db

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

POSTS_SHEET_NAME = "Posts Queue"
ANALYTICS_SHEET_NAME = "Analytics"

# Column headers
POSTS_HEADERS = [
    "ID", "Content", "Format", "Characters", "Source", "Status", "Date Added", "Notes"
]
ANALYTICS_HEADERS = [
    "Date", "Posts Generated", "Posts Approved", "Posts Rejected"
]


def _get_client() -> gspread.Client:
    """Authenticate and return gspread client."""
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    """Open the configured spreadsheet."""
    client = _get_client()
    return client.open_by_key(GOOGLE_SHEET_ID)


def init_sheets():
    """Initialize sheet structure if needed."""
    try:
        spreadsheet = _get_spreadsheet()

        # Posts Queue sheet
        try:
            posts_sheet = spreadsheet.worksheet(POSTS_SHEET_NAME)
        except gspread.WorksheetNotFound:
            posts_sheet = spreadsheet.add_worksheet(
                title=POSTS_SHEET_NAME, rows=1000, cols=8
            )
        if not posts_sheet.row_values(1):
            posts_sheet.update("A1:H1", [POSTS_HEADERS])
            posts_sheet.format("A1:H1", {"textFormat": {"bold": True}})

        # Analytics sheet
        try:
            analytics_sheet = spreadsheet.worksheet(ANALYTICS_SHEET_NAME)
        except gspread.WorksheetNotFound:
            analytics_sheet = spreadsheet.add_worksheet(
                title=ANALYTICS_SHEET_NAME, rows=1000, cols=4
            )
        if not analytics_sheet.row_values(1):
            analytics_sheet.update("A1:D1", [ANALYTICS_HEADERS])
            analytics_sheet.format("A1:D1", {"textFormat": {"bold": True}})

        logger.info("Google Sheets initialized")
    except Exception as e:
        logger.error("Failed to initialize Google Sheets: %s", e)
        raise


def write_approved_post(post: dict):
    """Write an approved post to the Posts Queue sheet. Returns row number."""
    try:
        spreadsheet = _get_spreadsheet()
        sheet = spreadsheet.worksheet(POSTS_SHEET_NAME)

        content = post["content"]
        row_data = [
            post["id"],
            content,
            post["format"],
            len(content),
            post.get("source_topic", ""),
            "Ready to Post",
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
        ]

        sheet.append_row(row_data, value_input_option="USER_ENTERED")

        # Find the row we just added
        all_values = sheet.get_all_values()
        row_num = len(all_values)

        # Green background for approved posts
        sheet.format(f"A{row_num}:H{row_num}", {
            "backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}
        })

        # Update database with sheet row
        db.set_sheet_row(post["id"], row_num)

        logger.info("Post %d written to sheet row %d", post["id"], row_num)
        return row_num

    except Exception as e:
        logger.error("Failed to write post %s to sheet: %s", post.get("id"), e)
        return None


def update_analytics(stats: dict):
    """Add a row to the Analytics sheet with today's stats."""
    try:
        spreadsheet = _get_spreadsheet()
        sheet = spreadsheet.worksheet(ANALYTICS_SHEET_NAME)

        today = datetime.now().strftime("%Y-%m-%d")
        row_data = [
            today,
            stats["generated"],
            stats["approved"],
            stats["rejected"],
        ]

        sheet.append_row(row_data, value_input_option="USER_ENTERED")
        logger.info("Analytics updated for %s", today)

    except Exception as e:
        logger.error("Failed to update analytics: %s", e)


def mark_as_posted(post_id: int):
    """Update a post's status to 'Posted' in the sheet."""
    try:
        post = db.get_post_by_id(post_id)
        if not post or not post.get("sheet_row"):
            return

        spreadsheet = _get_spreadsheet()
        sheet = spreadsheet.worksheet(POSTS_SHEET_NAME)
        sheet.update_cell(post["sheet_row"], 6, "Posted")
        logger.info("Post %d marked as posted in sheet", post_id)

    except Exception as e:
        logger.error("Failed to mark post %d as posted: %s", post_id, e)
