from langgraph.graph import StateGraph, END
from typing import Dict, Any

from agents.researcher import researcher_node
from agents.curator import curator_node
from agents.writer import writer_node
from agents.editor import editor_node
from agents.publisher import publisher_node

class AgentState(Dict):
    messages: list
    category: str
    original_post: dict
    draft_article: str
    final_article: str
    image_url: str
    status: str
    needs_human_review: bool

# Build the workflow
workflow = StateGraph(AgentState)

workflow.add_node("researcher", researcher_node)
workflow.add_node("curator", curator_node)
workflow.add_node("writer", writer_node)
workflow.add_node("editor", editor_node)
workflow.add_node("publisher", publisher_node)

workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "curator")
workflow.add_edge("curator", "writer")
workflow.add_edge("writer", "editor")
workflow.add_edge("editor", "publisher")
workflow.add_edge("publisher", END)

def route_after_curator(state):
    return END if state.get("status") == "rejected" else "writer"

workflow.add_conditional_edges("curator", route_after_curator)

app = workflow.compile()

# Run every 2 hours
if __name__ == "__main__":
    import time
    while True:
        print("\n🔄 Starting new content cycle...")
        try:
            result = app.invoke({"messages": [], "status": "start"})
            print("✅ Cycle completed successfully.")
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        time.sleep(2 * 60 * 60)  # 2 hours