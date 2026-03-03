"""Fetches trending content from multiple free sources."""

import logging
import requests
import feedparser
from pytrends.request import TrendReq
from config import REDDIT_SUBREDDITS, RSS_FEEDS

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15


def fetch_hackernews(limit: int = 10) -> list[dict]:
    """Fetch top stories from HackerNews API."""
    topics = []
    try:
        resp = requests.get(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        story_ids = resp.json()[:limit]

        for sid in story_ids:
            try:
                story = requests.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    timeout=REQUEST_TIMEOUT,
                ).json()
                if story and story.get("title"):
                    topics.append({
                        "title": story["title"],
                        "source": "HackerNews",
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "score": story.get("score", 0),
                    })
            except Exception as e:
                logger.warning("Failed to fetch HN story %s: %s", sid, e)
    except Exception as e:
        logger.error("HackerNews API failed: %s", e)
    logger.info("HackerNews: fetched %d topics", len(topics))
    return topics


def fetch_reddit(limit_per_sub: int = 5) -> list[dict]:
    """Fetch top posts from Reddit RSS feeds."""
    topics = []
    headers = {"User-Agent": "x-autoposter/1.0"}
    for sub in REDDIT_SUBREDDITS:
        try:
            feed = feedparser.parse(
                f"https://www.reddit.com/r/{sub}/hot/.rss",
                request_headers=headers,
            )
            for entry in feed.entries[:limit_per_sub]:
                topics.append({
                    "title": entry.get("title", ""),
                    "source": f"Reddit r/{sub}",
                    "url": entry.get("link", ""),
                    "score": 0,
                })
        except Exception as e:
            logger.warning("Reddit r/%s failed: %s", sub, e)
    logger.info("Reddit: fetched %d topics", len(topics))
    return topics


def fetch_google_trends() -> list[dict]:
    """Fetch today's trending searches from Google Trends."""
    topics = []
    try:
        pytrends = TrendReq(hl="en-US", tz=330)
        trending = pytrends.trending_searches(pn="united_states")
        for _, row in trending.head(10).iterrows():
            title = row[0]
            topics.append({
                "title": title,
                "source": "Google Trends",
                "url": f"https://trends.google.com/trends/explore?q={title}",
                "score": 0,
            })
    except Exception as e:
        logger.error("Google Trends failed: %s", e)
    logger.info("Google Trends: fetched %d topics", len(topics))
    return topics


def fetch_rss_feeds() -> list[dict]:
    """Fetch articles from configured RSS feeds."""
    topics = []
    for name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                topics.append({
                    "title": entry.get("title", ""),
                    "source": name,
                    "url": entry.get("link", ""),
                    "score": 0,
                })
        except Exception as e:
            logger.warning("RSS feed %s failed: %s", name, e)
    logger.info("RSS feeds: fetched %d topics", len(topics))
    return topics


def research_all() -> list[dict]:
    """Run all research sources and return combined topics."""
    all_topics = []

    sources = [
        ("HackerNews", fetch_hackernews),
        ("Reddit", fetch_reddit),
        ("Google Trends", fetch_google_trends),
        ("RSS Feeds", fetch_rss_feeds),
    ]

    for name, fetcher in sources:
        try:
            results = fetcher()
            all_topics.extend(results)
        except Exception as e:
            logger.error("Source %s failed completely: %s", name, e)

    # Deduplicate by title (case-insensitive)
    seen = set()
    unique = []
    for t in all_topics:
        key = t["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(t)

    logger.info("Research complete: %d unique topics from %d total", len(unique), len(all_topics))
    return unique
