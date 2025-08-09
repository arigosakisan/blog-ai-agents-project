# agents/researcher.py
import os, time, requests
from langchain_core.messages import HumanMessage

UA = os.getenv("REDDIT_USER_AGENT", "trendsqueeze-bot/1.0 (+https://trendsqueeze.com)")
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")

FEEDS = {
    "AI": "r/artificial",
    "Tech": "r/technology",
    "Science": "r/science",
    "Futurology": "r/futurology",
    "Interesting": "r/interestingasfuck",
    "Marketing": "r/marketing",
}

THRESHOLDS = [int(x) for x in os.getenv("REDDIT_UPS_THRESHOLDS", "1000,500,200,0").split(",")]

_TOKEN = None
_TOKEN_EXP = 0

def _get_token():
    global _TOKEN, _TOKEN_EXP
    now = time.time()
    if _TOKEN and now < _TOKEN_EXP - 60:
        return _TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Missing REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET")
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {"grant_type": "client_credentials"}  # app-only
    headers = {"User-Agent": UA}
    r = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    _TOKEN = j["access_token"]
    _TOKEN_EXP = now + int(j.get("expires_in", 3600))
    return _TOKEN

def _fetch_sub_top(sub: str, t: str = "day", limit: int = 25):
    token = _get_token()
    headers = {"Authorization": f"bearer {token}", "User-Agent": UA}
    url = f"https://oauth.reddit.com/{sub}/top?t={t}&limit={limit}&raw_json=1"
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()["data"]["children"]

def _collect_pool():
    items = []
    for category, sub in FEEDS.items():
        try:
            for post in _fetch_sub_top(sub):
                d = post["data"]
                if d.get("over_18"):
                    continue
                ups = int(d.get("ups", 0))
                items.append({
                    "title": (d.get("title") or "")[:280],
                    "summary": (d.get("selftext") or d.get("title") or "")[:700],
                    "url": "https://www.reddit.com" + d.get("permalink", ""),
                    "ups": ups,
                    "category_hint": category
                })
        except Exception as e:
            print(f"[researcher] feed error {category}: {e}", flush=True)
            continue
    return items

def researcher_node(state: dict) -> dict:
    pool = _collect_pool()
    print(f"[researcher] pool size={len(pool)}", flush=True)
    if not pool:
        return {"status": "no_posts", "messages": [HumanMessage(content="No posts fetched")]}
    for thr in THRESHOLDS:
        cand = [p for p in pool if p["ups"] >= thr]
        if cand:
            best = max(cand, key=lambda x: x["ups"])
            return {
                "status": "research_done",
                "original_post": best,
                "messages": [HumanMessage(content=f"Found (≥{thr} ups): {best['title']} [{best['ups']}]")]
            }
    best = max(pool, key=lambda x: x["ups"])
    return {
        "status": "research_done",
        "original_post": best,
        "messages": [HumanMessage(content=f"Found (fallback): {best['title']} [{best['ups']}]")]
    }
