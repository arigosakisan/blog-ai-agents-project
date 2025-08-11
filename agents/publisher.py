# agents/publisher.py
import os
import re
import json
import base64
import requests
from typing import List, Tuple, Optional
from langchain_core.messages import HumanMessage

# ---------- OpenAI (SDK v1.x) ----------
try:
    import openai
    client = openai.OpenAI()
except Exception:
    client = None

# ---------- Markdown -> HTML ----------
# pip install markdown
try:
    import markdown as md
except Exception:
    md = None

UA = os.getenv("WP_USER_AGENT", "trendsqueeze-agent/1.0 (+https://trendsqueeze.com)")

# Slugovi iz tvog sajta (prema /wp-json/wp/v2/categories):
CATEGORY_SLUG_MAP = {
    "Marketing": "marketing" (id=31)
    "Tech": "tech" (id=33)
    "Science": "science" (id=32)
    "Futurology": "futurology" (id=36)
    "AI": "ai" (id=37)
    "Interesting": "interesting" (id=35)
    "Trends": "trends" (id=26)

}

def _wp_default_cat_id() -> Optional[int]:
    v = (os.getenv("WP_DEFAULT_CATEGORY_ID") or "").strip()
    return int(v) if v.isdigit() else None

# ---------------- Helpers: URL/Auth ----------------
def _wp_base_url() -> str:
    url = (os.getenv("WORDPRESS_URL") or "https://api.trendsqueeze.com").strip().rstrip("/")
    j = url.find("/wp-json")
    if j != -1:
        url = url[:j]
    return url

def _wp_auth_headers() -> dict:
    user = (os.getenv("WORDPRESS_USERNAME") or "").strip()
    pwd  = (os.getenv("WORDPRESS_PASSWORD") or "").strip()
    if not user or not pwd:
        raise RuntimeError("Missing WORDPRESS_USERNAME or WORDPRESS_PASSWORD")
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def _headers_json() -> dict:
    return {
        **_wp_auth_headers(),
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Accept": "application/json",
    }

def _headers_media(filename: str) -> dict:
    return {
        **_wp_auth_headers(),
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/png",
        "User-Agent": UA,
        "Accept": "application/json",
    }

# ---------------- OpenAI Images ----------------
def _gen_image_b64(prompt: str, size: str) -> str:
    """
    size: 1024x1024, 1024x1536, 1536x1024, or 'auto'
    Returns base64 (no data: prefix).
    """
    if client is None:
        raise RuntimeError("OpenAI client not available for image generation")
    resp = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        n=1,
    )
    return resp.data[0].b64_json

# ---------------- WP Media/Posts/Categories ----------------
def _upload_media(image_b64: str, filename: str) -> Tuple[int, str]:
    media_url = _wp_base_url() + "/wp-json/wp/v2/media"
    binary = base64.b64decode(image_b64)
    r = requests.post(media_url, headers=_headers_media(filename), data=bytearray(binary), timeout=120)
    try:
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"WP media upload failed: {r.status_code} {(r.text or '')[:400]}") from e
    j = r.json()
    mid = j.get("id")
    src = j.get("source_url")
    if not mid or not src:
        raise RuntimeError(f"WP media upload malformed response: {j}")
    return mid, src

def _wp_get_category_id_by_slug(slug: str) -> Optional[int]:
    url = _wp_base_url() + "/wp-json/wp/v2/categories"
    r = requests.get(url, params={"slug": slug, "per_page": 100}, headers=_headers_json(), timeout=60)
    if r.status_code != 200:
        return None
    arr = r.json()
    if isinstance(arr, list) and arr:
        return arr[0].get("id")
    return None

def _wp_get_category_id_by_name(name: str) -> Optional[int]:
    url = _wp_base_url() + "/wp-json/wp/v2/categories"
    r = requests.get(url, params={"search": name, "per_page": 100}, headers=_headers_json(), timeout=60)
    if r.status_code != 200:
        return None
    for cat in r.json():
        if cat.get("name", "").strip().lower() == name.strip().lower():
            return cat.get("id")
        if cat.get("slug", "").strip().lower() == name.strip().lower():
            return cat.get("id")
    return None

def _resolve_category_ids(state: dict) -> List[int]:
    hint = (state.get("category") or state.get("original_post", {}).get("category_hint") or "").strip()
    ids: List[int] = []
    if hint:
        slug = CATEGORY_SLUG_MAP.get(hint) or hint.lower().replace(" ", "-")
        cid = _wp_get_category_id_by_slug(slug)
        if not cid:
            cid = _wp_get_category_id_by_name(hint)
        if cid:
            ids.append(cid)
    if not ids:
        d = _wp_default_cat_id()
        if d:
            ids.append(d)
    return ids

# ---------------- Content helpers ----------------
_H2_RE_HTML = re.compile(r"<h2[^>]*>", re.I)

def _strip_image_prompt_marker(markdown_text: str) -> str:
    # ukloni eventualne linije tipa [IMAGE_PROMPT]: ...
    return re.sub(r"^\[IMAGE_PROMPT\]:.*?$", "", markdown_text, flags=re.M).strip()

def _md_to_html(md_text: str) -> str:
    if md is None:
        # Minimal fallback — ali OBAVEZNO instaliraj 'markdown' paket da bi render bio ispravan.
        safe = md_text.replace("<", "&lt;").replace(">", "&gt;")
        return "<pre>" + safe + "</pre>"
    return md.markdown(
        md_text,
        extensions=["extra", "sane_lists", "toc"],
        output_format="xhtml1"
    )

def _insert_inline_figures(html: str, urls: List[str]) -> str:
    blocks = "".join([f'\n<figure class="wp-block-image"><img src="{u}" alt=""/></figure>\n' for u in urls])
    m = _H2_RE_HTML.search(html)
    if m:
        idx = m.end()
        return html[:idx] + blocks + html[idx:]
    return html.rstrip() + blocks

def _create_post(title: str, content_html: str, featured_media_id: int, category_ids: List[int]) -> dict:
    posts_url = _wp_base_url() + "/wp-json/wp/v2/posts"
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",            # zahteva Author+
        "featured_media": featured_media_id,
    }
    if category_ids:
        payload["categories"] = category_ids
    r = requests.post(posts_url, json=payload, headers=_headers_json(), timeout=120)
    if r.status_code == 201:
        return r.json()
    raise RuntimeError(f"WP post create failed: {r.status_code} {(r.text or '')[:400]}")

# ---------------- Publisher Node ----------------
def publisher_node(state: dict) -> dict:
    """
    Requires:
      - state["final_article"] (Markdown, EN)
      - optional: state["image_prompt"], state["category"] or original_post.category_hint

    Enforces:
      - featured (1536x1024) + 2 inline (1024x1024); assigns category; sends HTML (no raw Markdown).
    """
    raw_md = (state.get("final_article") or "").strip()
    if not raw_md:
        return {"status": "error", "messages": [HumanMessage(content="No final_article to publish")]}

    raw_md = _strip_image_prompt_marker(raw_md)

    # Title
    first_line = raw_md.split("\n", 1)[0].lstrip("# ").strip()
    title = (first_line or "Untitled").strip()[:200]

    # Image base prompt
    base_prompt = (state.get("image_prompt") or f"Editorial blog imagery for: {title}. Clean, modern, tech-journal style, no text overlays.").strip()

    base = _wp_base_url()
    print(f"[wp] base={base} posts_url={base + '/wp-json/wp/v2/posts'} media_url={base + '/wp-json/wp/v2/media'}", flush=True)

    try:
        # 1) Featured (hero)
        hero_b64 = _gen_image_b64(base_prompt + " — wide hero image, aesthetic, editorial, no text.", "1536x1024")
        hero_id, hero_src = _upload_media(hero_b64, "hero.png")

        # 2) Two inline images
        inline_prompts = [
            base_prompt + " — square illustrative detail #1, minimal, no text.",
            base_prompt + " — square illustrative detail #2, minimal, no text.",
        ]
        inline_urls: List[str] = []
        for i, p in enumerate(inline_prompts, start=1):
            b64 = _gen_image_b64(p, "1024x1024")
            _, src = _upload_media(b64, f"inline{i}.png")
            inline_urls.append(src)

        # 3) Markdown -> HTML + insert inline figures + hero on top
        html_body = _md_to_html(raw_md)
        html_body = _insert_inline_figures(html_body, inline_urls)
        hero_html = f'<figure class="wp-block-image"><img src="{hero_src}" alt=""/></figure>\n'
        content_html = hero_html + html_body

        # 4) Resolve categories
        cat_ids = _resolve_category_ids(state)
        if not cat_ids:
            print("⚠️ No category resolved; set WP_DEFAULT_CATEGORY_ID to avoid Uncategorized.", flush=True)

        # 5) Create post
        post = _create_post(title, content_html, featured_media_id=hero_id, category_ids=cat_ids)

        print("✅ Article with featured + 2 inline images and category published to WordPress!", flush=True)
        return {
            "status": "published",
            "post_id": post.get("id"),
            "post_link": post.get("link"),
            "featured_media_id": hero_id,
            "messages": [HumanMessage(content="Published with featured + 2 inline images & category")],
        }

    except Exception as e:
        print(f"⚠️ WordPress image/post error: {e}", flush=True)
        return {"status": "wp_error", "messages": [HumanMessage(content=f"WP error: {e}")]}
