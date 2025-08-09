# agents/researcher.py
import os
import requests
from langchain_core.messages import HumanMessage

CATEGORIES = {
    "AI": "https://www.reddit.com/r/artificial/top.json?t=day&limit=25",
    "Tech": "https://www.reddit.com/r/technology/top.json?t=day&limit=25",
    "Science": "https://www.reddit.com/r/science/top.json?t=day&limit=25",
    "Futurology": "https://www.reddit.com/r/futurology/top.json?t=day&limit=25",
    "Interesting": "https://www.reddit.com/r/interestingasfuck/top.json?t=day&limit=25",
    "Marketing": "https://www.reddit.com/r/marketing/top.json?t=day&limit=25",
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def researcher_node(state: dict) -> dict:
    pool = []
    for category, url in CATEGORIES.items():
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            posts = resp.json()["data"]["children"]

            for p in posts:
                data = p["data"]
                ups = data.get("ups", 0)
                # Skupljamo i one sa manje upvote-a, npr. 200-1000
                if 200 <= ups <= 1000:
                    pool.append({
                        "category": category,
                        "title": data.get("title"),
                        "url": f"https://www.reddit.com{data.get('permalink')}",
                        "ups": ups,
                        "summary": data.get("selftext", "")[:500]
                    })
        except Exception as e:
            print(f"[researcher] feed error {category}: {e}", flush=True)

    if not pool:
        return {
            "status": "skip",
            "messages": [HumanMessage(content="No posts found in range")]
        }

    # Sortiramo po broju upvote-a
    best = sorted(pool, key=lambda x: x["ups"], reverse=True)[0]

    # Logujemo izabrani post
    print(f"[researcher] picked: {best['ups']} ups — {best['title'][:60]}", flush=True)

    return {
        "status": "research_done",
        "original_post": best
    }
