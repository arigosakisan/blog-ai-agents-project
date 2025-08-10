# agents/writer.py
from typing import Dict, Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

def _get_llm():
    # Stability + dobar stil, dovoljno brzo za server
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.4, max_tokens=1800)

WRITER_SYSTEM = """You are a senior tech journalist. Write clear, engaging, SEO-friendly English articles.
Rules:
- Use clean Markdown (H1, H2, lists). No raw HTML, no images, no footnotes, no front matter.
- No decorative symbols, no stray hashes, no triple backticks unless you’re showing code.
- Keep tone factual, concise, and reader-first. Avoid hype.
- Use short paragraphs (2–4 lines).
- Include at least 3–5 H2 sections with descriptive titles.
- If the source seems sensational, add a balanced “Caveats & Limitations” section.
- Add a short “Why it matters” section.
- End with a brief “Key takeaways” list (3–5 bullets).
- Never include [IMAGE_PROMPT] or any image instructions inside the article.
- Language: English only.
"""

WRITER_USER_TMPL = """Write a blog post based on the context below.

Context:
- Title: {title}
- Summary: {summary}
- Source URL: {url}

Requirements:
- Target length: 700–1000 words.
- Start with a single H1 that’s clear and specific (rewrite if needed).
- Use 3–5 H2 sections.
- Include concrete examples where useful.
- Add “Why it matters”, then “Caveats & Limitations”, then “Key takeaways”.
- Do NOT add any images or prompts in the text.

Return ONLY the Markdown article (no prefaces, no explanations).
"""

IMAGE_SYSTEM = """You create excellent BASE prompts for AI blog imagery (one line).
Return a single concise line (max ~65 words) that can drive 1 hero (1536x1024) and 2 inline (1024x1024) images.
Constraints:
- English only.
- No text overlays, no watermarks, no logos, no UI screenshots.
- Style: editorial, modern, minimal, high-quality.
- Include subject, composition, mood/lighting, color palette, and camera/render hints (e.g., depth of field, subtle rim light).
- No camera brands or copyrighted characters.
Return ONLY the prompt line, nothing else.
"""

IMAGE_USER_TMPL = """Create a base image prompt for this article:
Title: {title}
Summary: {summary}
Intended usage: hero (wide) + two inline squares; should work for both.
Optional theme hints: {category_hint}
"""

def writer_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expects in state either:
      - curated_post: {title, summary, url, category_hint?}
    or
      - original_post: {title, summary, url, category_hint?}

    Returns:
      - status: "draft_ready" | "skip" | "error"
      - draft_article: str (Markdown, EN)
      - image_prompt: str (one-line base prompt)
      - category: str (optional hint for publisher)
      - messages: [HumanMessage,...] (for tracing)
    """
    post = state.get("curated_post") or state.get("original_post") or {}
    title = (post.get("title") or "").strip()
    summary = (post.get("summary") or "").strip()
    url = (post.get("url") or post.get("link") or "").strip()
    category_hint = (post.get("category_hint") or state.get("category") or "").strip()

    if not (title or summary or url):
        return {
            "status": "skip",
            "messages": [HumanMessage(content="Writer: no input context; skipping")]
        }

    llm = _get_llm()

    # 1) Napiši članak (Markdown)
    try:
        md_resp = llm.invoke([
            SystemMessage(content=WRITER_SYSTEM),
            HumanMessage(content=WRITER_USER_TMPL.format(title=title, summary=summary, url=url))
        ])
        draft_article = (md_resp.content or "").strip()
        if not draft_article or len(draft_article) < 300:
            return {
                "status": "error",
                "messages": [HumanMessage(content="Writer: draft too short or empty")]
            }
    except Exception as e:
        return {
            "status": "error",
            "messages": [HumanMessage(content=f"Writer failed to produce draft: {e}")]
        }

    # 2) Generiši “base” image prompt (jedna linija)
    try:
        img_resp = llm.invoke([
            SystemMessage(content=IMAGE_SYSTEM),
            HumanMessage(content=IMAGE_USER_TMPL.format(
                title=title,
                summary=summary,
                category_hint=category_hint or "technology, AI, science"
            ))
        ])
        image_prompt = (img_resp.content or "").strip()
        # sanity trim
        image_prompt = " ".join(image_prompt.split())
        if not image_prompt or len(image_prompt) < 20:
            image_prompt = f"Editorial technology concept for '{title}', modern minimal composition, clean background, subtle depth of field, soft key light, balanced color palette, no text overlays."
    except Exception:
        # fallback
        image_prompt = f"Editorial technology concept for '{title}', modern minimal composition, clean background, subtle depth of field, soft key light, balanced color palette, no text overlays."

    out = {
        "status": "draft_ready",
        "draft_article": draft_article,
        "image_prompt": image_prompt,
        "messages": [HumanMessage(content="Writer produced draft & image prompt")],
    }
    if category_hint:
        out["category"] = category_hint
    return out
