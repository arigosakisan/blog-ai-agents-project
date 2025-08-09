# agents/editor.py
from langchain_core.messages import HumanMessage

PROMPT = """You are an editor. Improve the draft while keeping Markdown structure intact:
- Fix grammar, spelling, and clarity
- Keep headings, lists, links, and formatting
- Maintain English language and tone
- Return ONLY the improved Markdown, no extra text

DRAFT:
"""
def _get_llm():
    # Lazy import to avoid import-time failures breaking module import
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=1200)

def editor_node(state: dict) -> dict:
    draft = state.get("draft_article", "")
    if not draft:
        return {
            "status": "skip",
            "messages": [HumanMessage(content="No draft_article; skipping editor")]
        }

    try:
        llm = _get_llm()
        resp = llm.invoke(PROMPT.format(draft=draft))
        final_article = resp.content.strip()
        return {
            "status": "final_ready",
            "final_article": final_article,
            "messages": [HumanMessage(content="Final ready")]
        }
    except Exception as e:
        # Ne ruši ceo graf: jasno prijavi šta je pošlo naopako
        return {
            "status": "error",
            "messages": [HumanMessage(content=f"Editor failed: {e}")]
        }
