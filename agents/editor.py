# agents/editor.py
from langchain_core.messages import HumanMessage

PROMPT = """You are an editor. Improve the draft while keeping Markdown structure intact:
- Preserve all headings, subheadings, lists, and links.
- Correct grammar, spelling, and clarity.
- Keep the tone friendly but professional.
- Do not remove factual content.
- Only return the improved text, without extra comments.
"""

def editor_node(state: dict) -> dict:
    if "draft" not in state or not state["draft"]:
        return {
            "status": "no_draft",
            "messages": [HumanMessage(content="No draft found for editing.")]
        }
    
    draft_text = state["draft"]
    return {
        "status": "edit_done",
        "edited_post": draft_text,  # in real case, call LLM to improve draft
        "messages": [HumanMessage(content=f"Edited draft:\n\n{draft_text}")]
    }
