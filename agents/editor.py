from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=1200)

PROMPT = """You are an editor. Improve the draft while keeping Markdown structure intact:
- Fix grammar, tighten sentences
- Keep headings, bullets, and links
- Ensure a strong intro and conclusion
- Keep Serbian language
Return ONLY the revised Markdown, no extra commentary.

DRAFT:
