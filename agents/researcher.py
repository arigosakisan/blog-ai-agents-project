# agents/researcher.py
import os
import time
import requests
from langchain_core.messages import HumanMessage

# ---- Config ----
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

# adaptivni pragovi; možeš menjati env varijablom npr. "500,200,0"
THRESHOLDS = [int(x) for x in os.getenv("REDDIT_UPS_THRESHOLDS", "1000,500,200,0").split(",")]

# token cache
_TOKEN = None
_TOKEN_EXP = 0  # epoch seconds

def _get_token():
    global _TOKEN, _TOKEN_EXP
    now = time.time()
    if _TOKEN and now < _TOKEN_EXP - 60:
        return _TOKEN

    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("Missing REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET env vars")

    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
    data = {"grant_type": "client_credentials"}  # app-only for public data
    headers = {"User-Agent": UA}
    r = requests.post("https://www.reddit.com/api/v1/access_token", auth=auth, data=data, headers=headers, timeout=20)
    r.raise_for_status()
    j = r.json()
    _TOKEN = j["access_token"]
    _TOKEN_EXP = now + int(j.get("expires_in", 3600))
    return _TOKEN

def _fetch_sub_top(sub: str, t: str = "day", limit: int = 25):
    """
    Fetch top posts for a subreddit using OAuth endpoint.
    """
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
                    continue  # skip NSFW
                ups = int(d.get("ups", 0))
                items.append({
                    "title": (d.get("title") or "")[:280],
                    "summary": (d.get("selftext") or d.get("title") or "")[:700],
                    "url": "https://www.reddit.com" + d.get("permalink", ""),
                    "ups": ups,
                    "category_hint": category
                })
        except requests.HTTPError as e:
            # Ako OAuth poziv padne (npr. 403 zbog rate-limit), probaj jednom RSS kao “best effort”
            print(f"[researcher] feed error {category}: {e}", flush=True)
            try:
                rss = requests.get(f"https://www.reddit.com/{sub}.rss", headers={"User-Agent": UA}, timeout=20)
                rss.raise_for_status()
                # Minimalni fallback: uzmi samo title/link (bez ups)
                # (Ovaj fallback neće proći preko pragova, ali spašava ciklus)
                # Možeš uvesti feedparser ako želiš lepše parsiranje.
            except Exception as e2:
                print(f"[researcher] rss fallback failed {category}: {e2}", flush=True)
                continue
        except Exception as e:
            print(f"[researcher] feed error {category}: {e}", flush=True)
            continue
    return items

def researcher_node(state: dict) -> dict:
    pool = _collect_pool()
    if not pool:
        return {
            "status": "no_posts",
            "messages": [HumanMessage(content="No posts fetched (OAuth blocked or empty)")]
        }

    # pokušaj pragove redom
    for thr in THRESHOLDS:
        cand = [p for p in pool if p["ups"] >= thr]
        if cand:
            best = max(cand, key=lambda x: x["ups"])
            return {
                "status": "research_done",
                "original_post": best,
                "messages": [HumanMessage(content=f"Found (≥{thr} ups): {best['title']} [{best['ups']}]")]
            }

    # fallback — najviše upvote-a bez obzira na prag
    best = max(pool, key=lambda x: x["ups"])
    return {
        "status": "research_done",
        "original_post": best,
        "messages": [HumanMessage(content=f"Found (fallback): {best['title']} [{best['ups']}]")]
    }
