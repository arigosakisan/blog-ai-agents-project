# agents/writer.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5, max_tokens=1200)

PROMPT = """Write a blog post in clean Markdown for Trend Squeeze.
Constraints:
- Language: English (en)
- Audience: tech/AI/marketing-savvy readers
- Structure: H1 title, intro, 3–5 H2 sections, short paragraphs, bullets where useful, conclusion
- Tone: clear, practical, mildly energetic
- Include sources/links if useful (few, credible)
- Avoid clickbait; be specific
- End the output with exactly one line:
  [IMAGE_PROMPT]: <short description for a wide 1792x1024 header>

Context:
Category: {category}
Original Title: {title}
Summary/Notes: {summary}
Source URL: {url}
"""

def writer_node(state: dict) -> dict:
    post = state.get("original_post", {})
    if not post:
        return {
            "status": "skip",
            "messages": [HumanMessage(content="No original_post; skipping writer")]
        }

    category = state.get("category") or post.get("category_hint") or "Interesting"

    resp = _llm.invoke(PROMPT.format(
        category=category,
        title=post.get("title", ""),
        summary=post.get("summary", ""),
        url=post.get("url", ""),
    ))

    content = resp.content.strip()

    # Extract [IMAGE_PROMPT]
    image_prompt = "Neutral editorial header, technology/innovation, minimal, wide 1792x1024"
    marker = "[IMAGE_PROMPT]:"
    if marker in content:
        image_prompt = content.split(marker, 1)[1].strip().strip("[] ").strip()

    return {
        "status": "draft_ready",
        "draft_article": content,
        "image_prompt": image_prompt,
        "messages": [HumanMessage(content=f"Draft ready ({len(content)} chars)")]
    }
