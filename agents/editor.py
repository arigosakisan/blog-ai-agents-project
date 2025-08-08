# agents/editor.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

def editor_node(state):
    llm = ChatOpenAI(model="gpt-4o", temperature=0.2)
    prompt = f"""
You are a senior editor. Review this draft:

Category: {state['category']}
Draft:
{state['draft_article']}

Check for:
- Clarity and flow
- Natural, human tone
- Fluff, hype, or robotic language
- Grammar and readability
- Suggest one improvement

Return only the improved version. No comments.
"""
    response = llm.invoke([HumanMessage(content=prompt)])
    return {
        "final_article": response.content,
        "messages": [HumanMessage(content="Editor: article polished")],
        "status": "edited"
    }