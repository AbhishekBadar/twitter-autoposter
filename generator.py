"""DeepSeek AI post generation using OpenAI-compatible API."""

import json
import logging
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an experienced social media content strategist writing for a viral X (Twitter) aggregator account. You have a sharp, intelligent voice — not a journalist, not a bot.

Rules you MUST follow:
- First line of every post must be a scroll-stopping hook
- No hashtags. Ever.
- No emojis unless they add genuine value
- No corporate language, no buzzwords, no filler
- Be specific with numbers and facts — vague claims are boring
- Sound like a real human with real opinions
- Return ONLY the post content. No explanations, no preamble, no labels.

For single posts (VIRAL_FACT and NEWS_REACTION):
- STRICTLY under 280 characters. This is non-negotiable.
- Every word must earn its place

For THREAD format:
- Exactly 5 tweets numbered (1/5), (2/5), (3/5), (4/5), (5/5)
- Each tweet under 280 characters
- Each tweet flows naturally into the next
- First tweet is the hook that makes people want to read the rest
- Last tweet is a punchy conclusion or call to think
- Separate tweets with a blank line"""

VIRAL_FACT_PROMPT = """From the topics below, pick the most shocking or surprising one and write a VIRAL FACT post.
This should be a mind-blowing stat, fact, or piece of information with a punchy caption.
MUST be under 280 characters total.

Topics:
{topics}"""

NEWS_REACTION_PROMPT = """From the topics below, pick the biggest/most important story and write a NEWS REACTION post.
Give a sharp 1-2 line take on the story. Be opinionated.
MUST be under 280 characters total.

Topics:
{topics}"""

THREAD_PROMPT = """From the topics below, pick the most interesting/fascinating one and write a 5-tweet THREAD going deep on it.
Number each tweet (1/5), (2/5), etc. Each tweet under 280 characters.
Make it educational, surprising, and engaging. Separate tweets with a blank line.

Topics:
{topics}"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def _format_topics(topics: list[dict]) -> str:
    lines = []
    for i, t in enumerate(topics, 1):
        source = t.get("source", "Unknown")
        lines.append(f"{i}. [{source}] {t['title']}")
        if t.get("url"):
            lines.append(f"   URL: {t['url']}")
    return "\n".join(lines)


def _generate(prompt: str) -> str:
    """Call DeepSeek API and return generated text."""
    client = _get_client()
    response = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1000,
        temperature=1.0,
    )
    return response.choices[0].message.content.strip()


def generate_viral_fact(topics: list[dict]) -> dict:
    """Generate a viral fact post."""
    topic_text = _format_topics(topics)
    prompt = VIRAL_FACT_PROMPT.format(topics=topic_text)
    logger.info("Generating VIRAL_FACT post...")
    content = _generate(prompt)
    return {"content": content, "format": "VIRAL_FACT", "source_topic": "auto-selected"}


def generate_news_reaction(topics: list[dict]) -> dict:
    """Generate a news reaction post."""
    topic_text = _format_topics(topics)
    prompt = NEWS_REACTION_PROMPT.format(topics=topic_text)
    logger.info("Generating NEWS_REACTION post...")
    content = _generate(prompt)
    return {"content": content, "format": "NEWS_REACTION", "source_topic": "auto-selected"}


def generate_thread(topics: list[dict]) -> dict:
    """Generate a 5-tweet thread."""
    topic_text = _format_topics(topics)
    prompt = THREAD_PROMPT.format(topics=topic_text)
    logger.info("Generating THREAD post...")
    content = _generate(prompt)
    return {"content": content, "format": "THREAD", "source_topic": "auto-selected"}


def generate_all_posts(topics: list[dict]) -> list[dict]:
    """Generate all 3 post formats from given topics."""
    posts = []
    generators = [generate_viral_fact, generate_news_reaction, generate_thread]

    for gen_func in generators:
        try:
            post = gen_func(topics)
            posts.append(post)
            logger.info("Generated %s (%d chars)", post["format"], len(post["content"]))
        except Exception as e:
            logger.error("Failed to generate %s: %s", gen_func.__name__, e)

    return posts
