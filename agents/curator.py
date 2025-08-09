# agents/curator.py
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

ALLOWED = {"AI", "Tech", "Science", "Futurology", "Marketing", "Interesting"}
_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

PROMPT = """You are a strict curator. Decide:
1) category (one of: AI, Tech, Science, Futurology, Marketing, Interesting)
2) worthy (true/false) — should we write an article?

Return pure JSON exactly like this (no extra text):
{{"category": "...", "worthy": true}}

Title: {title}
Summary: {summary}
URL: {url}
"""

def _safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s:e+1])
            except Exception:
                pass
    return {}

def curator_node(state: dict) -> dict:
    post = state.get("original_post") or {}
    title = post.get("title", "").strip()
    summary = post.get("summary", "").strip()
    url = post.get("url", "").strip()

    if not title:
        return {"status": "skip", "messages": [HumanMessage(content="No original_post; skipping curation")]}

    resp = _llm.invoke(PROMPT.format(title=title, summary=summary, url=url))
    data = _safe_json(resp.content)

    cat = (data.get("category") or post.get("category_hint") or "Interesting").strip().title()
    worthy = data.get("worthy", True)
    if isinstance(worthy, str):
        worthy = worthy.strip().lower() in {"true", "yes", "y", "1"}

    if cat not in ALLOWED:
        cat = "Interesting"

    # PASS-THROUGH original_post kako bi writer SIGURNO imao pristup
    return {
        "status": "curated" if worthy else "rejected",
        "category": cat,
        "worthy": worthy,
        "original_post": post,
        "messages": [HumanMessage(content=f"Curated: {title[:60]}... -> {cat} / worthy={worthy}")]
    }
