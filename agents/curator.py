# agents/curator.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import json

def curator_node(state):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    prompt = f"""
    You are a senior content curator. Analyze this Reddit post:

    Title: {state['original_post']['title']}
    Summary: {state['original_post']['summary']}

    Decide:
    1. Final category: AI, Tech, Science, Futurology, Marketing, Interesting
    2. Is it worth a full blog post? (Yes/No)
    3. Brief reason

    Respond in JSON:
    {{ "category": "...", "worthy": true/false, "reason": "..." }}
    """
    response = llm.invoke([HumanMessage(content=prompt)])
    try:
        result = json.loads(response.content)
    except:
        result = {"category": "Interesting", "worthy": True, "reason": "Fallback"}

    if not result["worthy"]:
        return {
            "status": "rejected",
            "messages": [HumanMessage(content=f"Rejected: {result['reason']}")]
        }
    return {
        "category": result["category"],
        "status": "curated",
        "messages": [HumanMessage(content=f"Curated as: {result['category']}")]
    }