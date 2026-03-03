"""Telegram bot for post approval flow."""

import logging
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import database as db

logger = logging.getLogger(__name__)

_app = None
_loop_thread = None


def _is_authorized(update: Update) -> bool:
    """Check if the message is from the authorized chat."""
    return str(update.effective_chat.id) == str(TELEGRAM_CHAT_ID)


def _char_count(text: str) -> int:
    """Count characters for tweet length display."""
    return len(text)


def _format_post_message(post: dict) -> str:
    """Format a post for Telegram display."""
    content = post["content"]
    fmt = post["format"]
    chars = _char_count(content)
    source = post.get("source_topic", "N/A")
    post_id = post["id"]

    header = f"📝 <b>{fmt}</b> | {chars} chars | Source: {source}\n<code>ID: {post_id}</code>\n"
    separator = "─" * 30
    return f"{header}{separator}\n\n{content}"


def _get_approval_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Create inline keyboard with approve/reject/edit buttons."""
    buttons = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{post_id}"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def send_posts_for_approval(posts: list):
    """Send generated posts to Telegram for review."""
    from telegram import Bot

    # Use the app's bot if running, otherwise create a standalone bot
    if _app:
        bot = _app.bot
    else:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

    chat_id = TELEGRAM_CHAT_ID

    await bot.send_message(
        chat_id=chat_id,
        text=f"🔔 <b>{len(posts)} new posts generated!</b>\nReview each one below:",
        parse_mode="HTML",
    )

    for post in posts:
        try:
            msg_text = _format_post_message(post)
            msg = await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                reply_markup=_get_approval_keyboard(post["id"]),
                parse_mode="HTML",
            )
            db.set_telegram_message_id(post["id"], msg.message_id)
        except Exception as e:
            logger.error("Failed to send post %s to Telegram: %s", post["id"], e)


async def send_notification(text: str):
    """Send a plain text notification to Telegram."""
    from telegram import Bot

    if _app:
        bot = _app.bot
    else:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)


async def _handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses."""
    query = update.callback_query
    if not _is_authorized(update):
        await query.answer("Unauthorized.")
        return

    await query.answer()
    data = query.data
    action, post_id_str = data.split("_", 1)
    post_id = int(post_id_str)

    post = db.get_post_by_id(post_id)
    if not post:
        await query.edit_message_text("Post not found.")
        return

    if action == "approve":
        db.update_post_status(post_id, "approved")

        # Write to Google Sheets
        try:
            from sheets import write_approved_post
            write_approved_post(post)
        except Exception as e:
            logger.error("Failed to write to sheet: %s", e)

        await query.edit_message_text(
            f"✅ APPROVED\n\n{post['content']}", parse_mode="HTML"
        )
        logger.info("Post %d approved", post_id)

    elif action == "reject":
        db.update_post_status(post_id, "rejected")
        await query.edit_message_text(
            f"❌ REJECTED\n\n{post['content']}", parse_mode="HTML"
        )
        logger.info("Post %d rejected", post_id)

    elif action == "edit":
        await query.edit_message_text(
            f"✏️ EDIT MODE\n\n"
            f"Current content:\n{post['content']}\n\n"
            f"Reply with:\nEDIT_{post_id}: your new content here",
            parse_mode="HTML",
        )

    # Send summary if all posts are reviewed
    pending = db.get_pending_posts()
    if not pending:
        stats = db.get_today_stats()
        summary = (
            f"📊 <b>Review Complete!</b>\n"
            f"✅ Approved: {stats['approved']}\n"
            f"❌ Rejected: {stats['rejected']}\n"
            f"📝 Total: {stats['generated']}\n"
            f"Sheet updated."
        )
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, text=summary, parse_mode="HTML"
        )

        # Update analytics sheet
        try:
            from sheets import update_analytics
            update_analytics(stats)
        except Exception as e:
            logger.error("Failed to update analytics sheet: %s", e)


async def _handle_edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit replies from user."""
    if not _is_authorized(update):
        return

    text = update.message.text
    if not text or not text.startswith("EDIT_"):
        return

    try:
        # Parse EDIT_<id>: <new content>
        prefix, new_content = text.split(":", 1)
        post_id = int(prefix.replace("EDIT_", "").strip())
        new_content = new_content.strip()
    except (ValueError, IndexError):
        await update.message.reply_text(
            "Invalid format. Use: EDIT_<id>: <new content>"
        )
        return

    post = db.get_post_by_id(post_id)
    if not post:
        await update.message.reply_text("Post not found.")
        return

    db.update_post_content(post_id, new_content)
    chars = len(new_content)

    # Send updated post with approval buttons
    await update.message.reply_text(
        f"✏️ EDITED | {chars} chars\n\n{new_content}",
        reply_markup=_get_approval_keyboard(post_id),
        parse_mode="HTML",
    )
    logger.info("Post %d edited (%d chars)", post_id, chars)


async def _handle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command."""
    if not _is_authorized(update):
        return

    stats = db.get_today_stats()
    recent = db.get_recent_posts(5)

    text = f"📊 Today's Stats\nGenerated: {stats['generated']} | Approved: {stats['approved']} | Rejected: {stats['rejected']}\n\n"
    text += "Recent Posts:\n"
    for p in recent:
        status_emoji = {"approved": "✅", "rejected": "❌", "pending": "⏳"}.get(
            p["status"], "❓"
        )
        text += f"{status_emoji} [{p['format']}] {p['content'][:50]}...\n"

    await update.message.reply_text(text, parse_mode="HTML")


def build_app():
    """Build and return the Telegram Application (without starting it)."""
    global _app

    _app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    _app.add_handler(CommandHandler("status", _handle_status))
    _app.add_handler(CallbackQueryHandler(_handle_callback))
    _app.add_handler(
        MessageHandler(filters.TEXT & filters.Regex(r"^EDIT_\d+:"), _handle_edit_message)
    )

    logger.info("Telegram bot application built")
    return _app


def run_bot_blocking():
    """Run the Telegram bot on the main thread (blocking)."""
    app = build_app()
    logger.info("Telegram bot starting polling on main thread...")
    app.run_polling(drop_pending_updates=True)
