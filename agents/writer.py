# agents/writer.py
from typing import Dict, Any, List
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

ALLOWED_CATEGORIES: List[str] = [
    "Marketing",
    "Tech",
    "Science",
    "Futurology",
    "AI",
    "Interesting",
]

def _get_llm():
    # Stable, good style, and fast enough for server use
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.4, max_tokens=1800)

# ---------- SYSTEM PROMPTS ----------
WRITER_SYSTEM = """You are a senior tech journalist. Write clear, engaging, SEO-friendly English articles.

Rules:
- Use clean Markdown (H1, H2, lists). No raw HTML, no images, no footnotes, no front matter.
- No decorative symbols, no stray hashes, no triple backticks unless you’re showing code.
- Tone: factual, concise, reader-first. Avoid hype and clichés.
- Paragraphs: short (2–4 lines).
- Sections: include 3–5 H2 headings with descriptive titles.
- Include a brief “Why it matters” section.
- Include a concise “Caveats & Limitations” section if applicable.
- End with a short “Key takeaways” list (3–5 bullets).
- Do NOT include any image prompts or instructions in the article body.
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
- Add “Why it matters”, then “Caveats & Limitations” (if relevant), then “Key takeaways”.
- Do NOT add any images or prompts in the text.

Return ONLY the Markdown article (no prefaces, no explanations).
"""

CLASSIFY_SYSTEM = f"""You assign exactly one category from a fixed set.
Allowed categories: {", ".join(ALLOWED_CATEGORIES)}.

Rules:
- Output MUST be exactly one word/phrase from the allowed set, with identical casing, no punctuation, no extra text.
- If unsure, choose the single best fit.
- English only.
"""

CLASSIFY_USER_TMPL = """Choose exactly one category for this article based on the context:

Allowed categories: {allowed}

Title: {title}
Summary: {summary}
Source URL: {url}

Return ONLY the category string (no quotes, no explanations).
"""

IMAGE_SYSTEM = """You create excellent BASE prompts for AI blog imagery (one line).
Return a single concise line (~40–65 words) that can drive 1 hero (1536x1024) and 2 inline (1024x1024) images.

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
Chosen category: {category}
Intended usage: hero (wide) + two inline squares; should work for both.
"""

# ---------- HELPERS ----------
def _normalize_category(s: str) -> str:
    # Keep exactly as one of ALLOWED_CATEGORIES; fallback to "Tech" if mismatch
    s = (s or "").strip()
    for cat in ALLOWED_CATEGORIES:
        if s.lower() == cat.lower():
            return cat
    return "Tech"

# ---------- NODE ----------
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
      - category: str (one of ALLOWED_CATEGORIES)
      - messages: [HumanMessage,...] (for tracing)
    """
    post = state.get("curated_post") or state.get("original_post") or {}
    title = (post.get("title") or "").strip()
    summary = (post.get("summary") or "").strip()
    url = (post.get("url") or post.get("link") or "").strip()

    # Optional hint coming from upstream (if present, we'll consider it)
    upstream_hint = (post.get("category_hint") or state.get("category") or "").strip()

    if not (title or summary or url):
        return {
            "status": "skip",
            "messages": [HumanMessage(content="Writer: no input context; skipping")]
        }

    llm = _get_llm()

    # 1) Classify category (forced into the allowed set)
    try:
        cls_resp = llm.invoke([
            SystemMessage(content=CLASSIFY_SYSTEM),
            HumanMessage(content=CLASSIFY_USER_TMPL.format(
                allowed=", ".join(ALLOWED_CATEGORIES),
                title=title,
                summary=summary,
                url=url
            ))
        ])
        category = _normalize_category(cls_resp.content.strip())
        # If upstream hinted and valid, you could prefer it — but we keep model's choice authoritative.
        # If you want upstream to override, uncomment:
        # if upstream_hint:
        #     category = _normalize_category(upstream_hint)
    except Exception:
        # Fallback if classification fails
        category = _normalize_category(upstream_hint or "Tech")

    # 2) Write the article (Markdown)
    try:
        md_resp = llm.invoke([
            SystemMessage(content=WRITER_SYSTEM),
            HumanMessage(content=WRITER_USER_TMPL.format(title=title, summary=summary, url=url))
        ])
        draft_article = (md_resp.content or "").strip()
        # Basic sanity
        if not draft_article or len(draft_article) < 300 or "\n#" not in draft_article:
            return {
                "status": "error",
                "messages": [HumanMessage(content="Writer: draft too short or malformed")]
            }
    except Exception as e:
        return {
            "status": "error",
            "messages": [HumanMessage(content=f"Writer failed to produce draft: {e}")]
        }

    # 3) Generate a high-quality BASE image prompt (single line)
    try:
        img_resp = llm.invoke([
            SystemMessage(content=IMAGE_SYSTEM),
            HumanMessage(content=IMAGE_USER_TMPL.format(
                title=title,
                summary=summary,
                category=category
            ))
        ])
        image_prompt = " ".join((img_resp.content or "").strip().split())
        if not image_prompt or len(image_prompt) < 20:
            image_prompt = (
                f"Editorial {category.lower()} concept for '{title}': modern minimal composition, "
                f"clean background, subtle depth of field, soft rim light, balanced color palette, "
                f"no text overlays."
            )
    except Exception:
        image_prompt = (
            f"Editorial {category.lower()} concept for '{title}': modern minimal composition, "
            f"clean background, subtle depth of field, soft rim light, balanced color palette, "
            f"no text overlays."
        )

    return {
        "status": "draft_ready",
        "draft_article": draft_article,
        "image_prompt": image_prompt,
        "category": category,
        "messages": [HumanMessage(content=f"Writer produced draft, category={category}, image prompt ready")],
    }
