# agents/researcher.py
import os
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

# Pragovi upvote-a kroz env var ili default
THRESHOLDS = [
    int(x) for x in os.getenv("REDDIT_UPS_THRESHOLDS", "1000,500,200,0").split(",")
]

def _fetch_candidates():
    items = []
    for category, url in FEEDS.items():
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            for post in r.json()["data"]["children"]:
                d = post["data"]
                if d.get("over_18"):  # preskoči NSFW
                    continue
                ups = d.get("ups", 0)
                items.append({
                    "title": (d.get("title") or "")[:280],
                    "summary": (d.get("selftext") or d.get("title") or "")[:700],
                    "url": "https://www.reddit.com" + d.get("permalink", ""),
                    "ups": ups,
                    "category_hint": category
                })
        except Exception as e:
            print(f"[researcher] feed error {category}: {e}", flush=True)
    return items

def researcher_node(state: dict) -> dict:
    pool = _fetch_candidates()
    if not pool:
        return {
            "status": "no_posts",
            "messages": [HumanMessage(content="No posts fetched")]
        }

    # Prolazi kroz pragove dok ne nađe bar jedan post
    for thr in THRESHOLDS:
        cand = [p for p in pool if p["ups"] >= thr]
        if cand:
            best = max(cand, key=lambda x: x["ups"])
            return {
                "status": "research_done",
                "original_post": best,
                "messages": [
                    HumanMessage(content=f"Found (≥{thr} ups): {best['title']} [{best['ups']}]")
                ]
            }

    # Fallback — uzmi globalni top bez praga
    best = max(pool, key=lambda x: x["ups"])
    return {
        "status": "research_done",
        "original_post": best,
        "messages": [
            HumanMessage(content=f"Found (fallback): {best['title']} [{best['ups']}]")
        ]
    }
