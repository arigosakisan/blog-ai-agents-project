# agents/researcher.py
import requests
from langchain_core.messages import HumanMessage

UA = {"User-Agent": "trendsqueeze-bot/1.0 (+https://trendsqueeze.com)"}

FEEDS = {
    "AI": "https://www.reddit.com/r/artificial/top.json?t=day&limit=25",
    "Tech": "https://www.reddit.com/r/technology/top.json?t=day&limit=25",
    "Science": "https://www.reddit.com/r/science/top.json?t=day&limit=25",
    "Futurology": "https://www.reddit.com/r/futurology/top.json?t=day&limit=25",
    "Interesting": "https://www.reddit.com/r/interestingasfuck/top.json?t=day&limit=25",
    "Marketing": "https://www.reddit.com/r/marketing/top.json?t=day&limit=25",
}

def researcher_node(state):
    hot_posts = []
    for category, url in FEEDS.items():
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            data = r.json()["data"]["children"]
            for post in data:
                d = post["data"]
                ups = d.get("ups", 0)
                if ups >= 500:  # spusti prag po volji
                    hot_posts.append({
                        "title": d.get("title", "")[:280],
                        "summary": (d.get("selftext") or d.get("title") or "")[:600],
                        "url": "https://www.reddit.com" + d.get("permalink",""),
                        "ups": ups,
                        "category_hint": category
                    })
        except Exception:
            continue

    if not hot_posts:
        return {"status": "no_posts", "messages": [HumanMessage(content="No trending posts found")]}

    best_post = max(hot_posts, key=lambda x: x["ups"])
    return {
        "original_post": best_post,
        "messages": [HumanMessage(content=f"Found post: {best_post['title']}")],
        "status": "research_done"
    }
