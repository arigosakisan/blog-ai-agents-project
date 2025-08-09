# agents/researcher.py
import re
import random
import os
import feedparser
from langchain_core.messages import HumanMessage

# User-Agent (možeš podesiti u Render env var REDDIT_USER_AGENT)
UA = os.getenv("REDDIT_USER_AGENT", "trendsqueeze-bot/1.0 (+https://trendsqueeze.com)")

# Subredditi po kategoriji (dodaj/izbaci po želji)
FEEDS = {
    "AI": "r/artificial",
    "Tech": "r/technology",
    "Science": "r/science",
    "Futurology": "r/futurology",
    "Interesting": "r/interestingasfuck",
    "Marketing": "r/marketing",
}

# Koliko stavki po subreddit-u da povučemo sa RSS-a
ITEMS_PER_FEED = int(os.getenv("RSS_ITEMS_PER_FEED", "20"))

def _rss_url(sub: str) -> str:
    # Reddit RSS za top/day
    # primer: https://www.reddit.com/r/artificial/top/.rss?t=day&limit=25
    limit = min(max(ITEMS_PER_FEED, 1), 50)
    return f"https://www.reddit.com/{sub}/top/.rss?t=day&limit={limit}"

def _clean_html(text: str) -> str:
    if not text:
        return ""
    # vrlo jednostavno uklanjanje HTML tagova iz summary-ja
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<.*?>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()

def _collect_candidates():
    items = []
    for category, sub in FEEDS.items():
        url = _rss_url(sub)
        try:
            feed = feedparser.parse(url, request_headers={"User-Agent": UA})
            for e in feed.entries:
                title = (getattr(e, "title", "") or "").strip()
                link = (getattr(e, "link", "") or "").strip()
                summary = _clean_html(getattr(e, "summary", "") or getattr(e, "description", ""))
                if not title or not link:
                    continue
                # Reddit često vraća "https://www.reddit.com/r/.../comments/.../..." linkove
                items.append({
                    "title": title[:280],
                    "url": link,
                    "summary": summary[:700],
                    "category_hint": category
                })
        except Exception as ex:
            print(f"[researcher] rss error {category}: {ex}", flush=True)
            continue
    return items

def researcher_node(state: dict) -> dict:
    pool = _collect_candidates()
    print(f"[researcher] pool size={len(pool)}", flush=True)

    if not pool:
        return {
            "status": "no_posts",
            "messages": [HumanMessage(content="No posts fetched from RSS")]
        }

    # Izaberi "najbolji" kandidat.
    # Pošto RSS već vraća top/day, dovoljno je uzeti prvi;
    # ili malo randomizovati među prvim rezultatima da ne bude uvek isti.
    top_k = min(10, len(pool))
    candidate = pool[0] if top_k == 1 else random.choice(pool[:top_k])

    # Log za pregled u Renderu
    print(f"[researcher] picked: {candidate['title'][:60]}", flush=True)

    return {
        "status": "research_done",
        "original_post": {
            "title": candidate["title"],
            "summary": candidate["summary"],
            "url": candidate["url"],
            "category_hint": candidate["category_hint"],
        },
        "messages": [HumanMessage(content=f"Picked: {candidate['title'][:80]}")]
    }
