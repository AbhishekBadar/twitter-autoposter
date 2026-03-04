"""DeepSeek AI post generation using OpenAI-compatible API."""

import logging
from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an elite social media content strategist writing for a viral X (Twitter) aggregator account. You study what makes content spread and you write posts that people can't help but engage with.

Your voice: sharp, intelligent, opinionated, human. You sound like the smartest person at the dinner table — not a journalist, not a brand, not a bot.

ABSOLUTE RULES:
- First line is EVERYTHING. You have 1 second before they scroll past. Use proven hook patterns:
  * Contrarian opener: "Stop doing [X]. Here's what actually works:"
  * Hidden knowledge: "The [industry] doesn't want you to know this:"
  * Bold stat opener: Lead with the most surprising number
  * Nobody talks about: "Nobody talks about this, but..."
  * Death declaration: "[Popular thing] is dead. Here's what's replacing it:"
- No hashtags. Ever. (1-2 max only if absolutely critical for discovery)
- No emojis unless they genuinely add value — most of the time they don't
- No corporate language, no buzzwords, no "game-changer", no "revolutionary"
- Be SPECIFIC with numbers and facts — "37% of doctors" beats "many doctors"
- Sound like a real human with real opinions, not a content mill
- Write to PROVOKE replies — the algorithm weights replies 13-27x more than likes
- Trigger high-arousal emotions: awe, surprise, humor, righteous anger. Never mild interest.
- Return ONLY the post content. No explanations, no preamble, no labels, no quotation marks.

For single posts (VIRAL_FACT, NEWS_REACTION, CONTRARIAN_TAKE):
- Target 71-100 characters for maximum engagement (sweet spot proven by data)
- Absolute max 280 characters but shorter is almost always better
- Leave room for people to quote-tweet with their own take
- Every single word must earn its place

For THREAD format:
- Exactly 5 tweets numbered (1/5), (2/5), (3/5), (4/5), (5/5)
- Each tweet under 280 characters
- Tweet 1 is the hook — it must be so compelling people NEED to read the rest
- Each tweet ends with a mini-cliffhanger that pulls into the next
- Tweet 5 is a punchy conclusion that makes people want to retweet the whole thread
- Separate tweets with a blank line
- Threads should educate, surprise, or tell a story — not just list facts"""

VIRAL_FACT_PROMPT = """From the topics below, pick the most SHOCKING or mind-blowing one and write a VIRAL FACT post.

Requirements:
- Lead with the most surprising number or fact — no buildup, hit them immediately
- Make it something people will screenshot and share
- If possible, contrast it with something familiar ("That's more than [relatable comparison]")
- Target 71-100 characters. Max 280.
- Write something that makes people reply "Wait, WHAT?"

Topics:
{topics}"""

NEWS_REACTION_PROMPT = """From the topics below, pick the biggest story and write a NEWS REACTION post.

Requirements:
- Don't just report the news — give a sharp, opinionated take people will argue about
- Take a clear side. Fence-sitting gets zero engagement.
- Your take should make people either strongly agree or strongly disagree (both drive replies)
- Target 71-100 characters. Max 280.
- Sound like you're texting a friend about the craziest thing you just read

Topics:
{topics}"""

CONTRARIAN_TAKE_PROMPT = """From the topics below, pick one where you can offer a CONTRARIAN perspective that challenges what most people believe.

Requirements:
- Challenge conventional wisdom with a specific, defensible argument
- Start with a bold claim that makes people stop and think
- Back it up with a specific fact or logical argument
- This should make people reply to either agree passionately or argue back
- Target 71-100 characters. Max 280.
- Be provocative but intelligent — not rage-bait

Topics:
{topics}"""

THREAD_PROMPT = """From the topics below, pick the most fascinating one and write a 5-tweet THREAD that goes deep.

Requirements:
- Tweet 1: The hook. Make it impossible to not click "Show more". Use a bold claim, shocking stat, or irresistible question.
- Tweet 2-4: Build the story. Each tweet reveals something new and surprising. Use specific numbers, names, dates.
- Tweet 5: The payoff. A punchy conclusion that reframes everything or gives a powerful takeaway.
- Each tweet must flow into the next naturally — end each with something that makes the next tweet feel necessary
- Number each tweet (1/5), (2/5), etc.
- Each tweet under 280 characters
- Separate tweets with a blank line
- Make it something people will bookmark and share

Topics:
{topics}"""


def _get_client() -> OpenAI:
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)


def _format_topics(topics) -> str:
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


def generate_viral_fact(topics) -> dict:
    """Generate a viral fact post."""
    topic_text = _format_topics(topics)
    prompt = VIRAL_FACT_PROMPT.format(topics=topic_text)
    logger.info("Generating VIRAL_FACT post...")
    content = _generate(prompt)
    return {"content": content, "format": "VIRAL_FACT", "source_topic": "auto-selected"}


def generate_news_reaction(topics) -> dict:
    """Generate a news reaction post."""
    topic_text = _format_topics(topics)
    prompt = NEWS_REACTION_PROMPT.format(topics=topic_text)
    logger.info("Generating NEWS_REACTION post...")
    content = _generate(prompt)
    return {"content": content, "format": "NEWS_REACTION", "source_topic": "auto-selected"}


def generate_contrarian_take(topics) -> dict:
    """Generate a contrarian take post."""
    topic_text = _format_topics(topics)
    prompt = CONTRARIAN_TAKE_PROMPT.format(topics=topic_text)
    logger.info("Generating CONTRARIAN_TAKE post...")
    content = _generate(prompt)
    return {"content": content, "format": "CONTRARIAN_TAKE", "source_topic": "auto-selected"}


def generate_thread(topics) -> dict:
    """Generate a 5-tweet thread."""
    topic_text = _format_topics(topics)
    prompt = THREAD_PROMPT.format(topics=topic_text)
    logger.info("Generating THREAD post...")
    content = _generate(prompt)
    return {"content": content, "format": "THREAD", "source_topic": "auto-selected"}


def generate_all_posts(topics) -> list:
    """Generate all 4 post formats from given topics."""
    posts = []
    generators = [
        generate_viral_fact,
        generate_news_reaction,
        generate_contrarian_take,
        generate_thread,
    ]

    for gen_func in generators:
        try:
            post = gen_func(topics)
            posts.append(post)
            logger.info("Generated %s (%d chars)", post["format"], len(post["content"]))
        except Exception as e:
            logger.error("Failed to generate %s: %s", gen_func.__name__, e)

    return posts
