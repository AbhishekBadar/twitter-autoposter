"""X-Autoposter: Orchestrator with scheduling and CLI commands."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

import config
import database as db
from researcher import research_all
from generator import generate_all_posts
from telegram_bot import run_bot_blocking, send_posts_for_approval, send_notification
from sheets import init_sheets

# ── Logging setup ──────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(config.LOG_FILE)),
    ],
)
logger = logging.getLogger("x-autoposter")


# ── Pipeline ───────────────────────────────────────────────────

def run_pipeline():
    """Full pipeline: research → generate → send for approval."""
    logger.info("=" * 50)
    logger.info("Pipeline started at %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 50)

    # Step 1: Research
    logger.info("Step 1: Researching trending content...")
    try:
        topics = research_all()
        if not topics:
            logger.warning("No topics found from any source")
            asyncio.run(send_notification("⚠️ Pipeline: No topics found from any source."))
            return
        saved = db.save_topics(topics)
        logger.info("Saved %d topics to database", saved)
    except Exception as e:
        logger.error("Research step failed: %s", e)
        asyncio.run(send_notification(f"❌ Pipeline failed at research step: {e}"))
        return

    # Step 2: Generate posts
    logger.info("Step 2: Generating posts with DeepSeek...")
    try:
        unused_topics = db.get_unused_topics(limit=20)
        if not unused_topics:
            logger.warning("No unused topics available")
            asyncio.run(send_notification("⚠️ Pipeline: No unused topics for generation."))
            return

        posts = generate_all_posts(unused_topics)
        if not posts:
            logger.warning("No posts generated")
            asyncio.run(send_notification("⚠️ Pipeline: DeepSeek generated no posts."))
            return

        # Save to database
        saved_posts = []
        for p in posts:
            post_id = db.save_post(p["content"], p["format"], p["source_topic"])
            p["id"] = post_id
            saved_posts.append(p)

        logger.info("Generated and saved %d posts", len(saved_posts))
    except Exception as e:
        logger.error("Generation step failed: %s", e)
        asyncio.run(send_notification(f"❌ Pipeline failed at generation step: {e}"))
        return

    # Step 3: Send to Telegram for approval
    logger.info("Step 3: Sending posts to Telegram...")
    try:
        asyncio.run(send_posts_for_approval(saved_posts))
        logger.info("Posts sent to Telegram for approval")
    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        asyncio.run(send_notification(f"❌ Pipeline failed at Telegram step: {e}"))

    logger.info("Pipeline complete — awaiting approval in Telegram")


def run_research_only():
    """Run only the research step and print results."""
    logger.info("Running research only...")
    topics = research_all()

    if not topics:
        print("\nNo topics found.")
        return

    saved = db.save_topics(topics)
    print(f"\n{'='*60}")
    print(f" Found {len(topics)} topics (saved {saved} new)")
    print(f"{'='*60}\n")

    # Group by source
    by_source = {}
    for t in topics:
        by_source.setdefault(t["source"], []).append(t)

    for source, items in sorted(by_source.items()):
        print(f"  [{source}] ({len(items)} topics)")
        for item in items[:5]:
            score = f" (score: {item['score']})" if item.get("score") else ""
            print(f"    • {item['title'][:80]}{score}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")
        print()


def print_status():
    """Print recent posts status table."""
    posts = db.get_recent_posts(20)
    stats = db.get_today_stats()

    print(f"\n{'='*70}")
    print(f" X-Autoposter Status")
    print(f"{'='*70}")
    print(f" Today: {stats['generated']} generated | {stats['approved']} approved | {stats['rejected']} rejected")
    print(f"{'─'*70}")

    if not posts:
        print(" No posts yet.")
    else:
        print(f" {'ID':<5} {'Format':<15} {'Status':<12} {'Chars':<7} {'Created':<20} {'Content'}")
        print(f" {'─'*4} {'─'*14} {'─'*11} {'─'*6} {'─'*19} {'─'*20}")
        for p in posts:
            content_preview = p["content"][:35].replace("\n", " ") + "..."
            print(
                f" {p['id']:<5} {p['format']:<15} {p['status']:<12} "
                f"{len(p['content']):<7} {p['created_at']:<20} {content_preview}"
            )

    print(f"{'='*70}\n")


# ── Main ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="X-Autoposter: Viral content pipeline")
    parser.add_argument("--now", action="store_true", help="Run full pipeline immediately")
    parser.add_argument("--status", action="store_true", help="Print recent posts status")
    parser.add_argument("--research", action="store_true", help="Run research step only")
    args = parser.parse_args()

    # Validate config
    missing = config.validate_config()
    if missing and not args.research:
        logger.error("Missing required config: %s", ", ".join(missing))
        print(f"\n❌ Missing required environment variables: {', '.join(missing)}")
        print("   Copy .env.example to .env and fill in all values.")
        sys.exit(1)

    # Initialize database
    db.init_db()

    if args.status:
        print_status()
        return

    if args.research:
        run_research_only()
        return

    if args.now:
        logger.info("Running pipeline immediately (--now flag)")
        run_pipeline()
        return

    # Production mode: scheduler + telegram bot
    logger.info("Starting X-Autoposter in production mode")

    # Initialize Google Sheets
    try:
        init_sheets()
    except Exception as e:
        logger.error("Failed to initialize sheets: %s", e)
        print(f"⚠️  Google Sheets init failed: {e}")
        print("   Posts will still be sent to Telegram but won't write to sheets.")

    # Start scheduler in background
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_pipeline,
        "cron",
        hour=config.SCHEDULE_HOUR,
        minute=config.SCHEDULE_MINUTE,
        id="daily_pipeline",
    )
    scheduler.start()

    logger.info(
        "Scheduler started — pipeline runs daily at %02d:%02d",
        config.SCHEDULE_HOUR,
        config.SCHEDULE_MINUTE,
    )
    print(f"\n✅ X-Autoposter running!")
    print(f"   📅 Daily pipeline at {config.SCHEDULE_HOUR:02d}:{config.SCHEDULE_MINUTE:02d}")
    print(f"   🤖 Telegram bot listening")
    print(f"   Press Ctrl+C to stop\n")

    # Run Telegram bot on main thread (blocking)
    run_bot_blocking()


if __name__ == "__main__":
    main()
