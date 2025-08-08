# agents/researcher.py
import feedparser
from langchain_core.messages import HumanMessage

def researcher_node(state):
    feeds = {
        "AI": "https://www.reddit.com/r/artificial/.rss",
        "Tech": "https://www.reddit.com/r/technology/.rss",
        "Science": "https://www.reddit.com/r/science/.rss",
        "Futurology": "https://www.reddit.com/r/futurology/.rss",
        "Interesting": "https://www.reddit.com/r/interestingasfuck/.rss",
        "Marketing": "https://www.reddit.com/r/marketing/.rss"
    }
    hot_posts = []
    for category, url in feeds.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                ups = int(entry.get("ups", 0))
                if ups > 1000:
                    hot_posts.append({
                        "title": entry.title,
                        "summary": entry.summary[:500],
                        "url": entry.link,
                        "ups": ups,
                        "category_hint": category
                    })
        except:
            continue
    if not hot_posts:
        return {"status": "no_posts", "messages": [HumanMessage(content="No trending posts found")]}

    best_post = max(hot_posts, key=lambda x: x["ups"])
    return {
        "original_post": best_post,
        "messages": [HumanMessage(content=f"Found post: {best_post['title']}")],
        "status": "research_done"
    }