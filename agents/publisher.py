# agents/publisher.py
import os
import re
import base64
import requests
from typing import List, Tuple
from langchain_core.messages import HumanMessage

# ---------------- OpenAI client ----------------
try:
    import openai
    client = openai.OpenAI()  # OpenAI SDK v1.x
except Exception:
    client = None

# ---------------- Config ----------------
# Set these in Render env:
# WORDPRESS_URL=https://api.trendsqueeze.com
# WORDPRESS_USERNAME=<wp_user_login>               (best: a user with Author role or higher)
# WORDPRESS_PASSWORD=<wp_application_password>     (Users → Profile → Application Passwords)
# Optional:
#   WP_USER_AGENT=trendsqueeze-agent/1.0 (+https://trendsqueeze.com)

UA = os.getenv("WP_USER_AGENT", "trendsqueeze-agent/1.0 (+https://trendsqueeze.com)")

# ---------------- Helpers: URL / Auth ----------------
def _wp_base_url() -> str:
    """
    Returns clean base like 'https://api.trendsqueeze.com' even if env
    accidentally contains '/wp-json' suffix.
    """
    url = (os.getenv("WORDPRESS_URL") or "https://api.trendsqueeze.com").strip()
    url = url.rstrip("/")
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
    Generate an image via OpenAI (required).
    size allowed: 1024x1024, 1024x1536, 1536x1024, or 'auto'.
    Returns base64 without data: prefix.
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

# ---------------- WordPress Media / Posts ----------------
def _upload_media(image_b64: str, filename: str) -> Tuple[int, str]:
    """
    Upload PNG to WP Media. Returns (media_id, source_url).
    Raises RuntimeError on any non-2xx.
    """
    media_url = _wp_base_url() + "/wp-json/wp/v2/media"
    binary = base64.b64decode(image_b64)
    r = requests.post(media_url, headers=_headers_media(filename), data=bytearray(binary), timeout=120)
    try:
        r.raise_for_status()
    except Exception as e:
        snippet = (r.text or "")[:400]
        raise RuntimeError(f"WP media upload failed: {r.status_code} {snippet}") from e
    j = r.json()
    mid = j.get("id")
    src = j.get("source_url")
    if not mid or not src:
        raise RuntimeError(f"WP media upload malformed response: {j}")
    return mid, src

def _create_post(title: str, content_html: str, featured_media_id: int) -> dict:
    """
    Create a published post with featured image. Requires Author+ permissions.
    """
    posts_url = _wp_base_url() + "/wp-json/wp/v2/posts"
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",            # change to "draft" if you want review first
        "featured_media": featured_media_id,
    }
    r = requests.post(posts_url, json=payload, headers=_headers_json(), timeout=120)
    if r.status_code == 201:
        return r.json()
    raise RuntimeError(f"WP post create failed: {r.status_code} {(r.text or '')[:400]}")

# ---------------- Content helpers ----------------
_H2_RE = re.compile(r"^##\s+", re.M)

def _insert_inline_images(markdown: str, urls: List[str]) -> str:
    """
    Insert 2–3 inline images right after first H2; if no H2, append at end.
    """
    blocks = [f'\n\n![inline image]({u})\n' for u in urls]
    inject = "".join(blocks)
    m = _H2_RE.search(markdown)
    if m:
        idx = m.end()
        return markdown[:idx] + "\n" + inject + markdown[idx:]
    return markdown.rstrip() + "\n" + inject + "\n"

# ---------------- Publisher Node ----------------
def publisher_node(state: dict) -> dict:
    """
    Requires in state:
      - final_article (Markdown, English)
      - image_prompt (optional; base idea for images)

    Enforces:
      - 1 featured (1536x1024) + 2 inline (1024x1024). If any generation/upload fails → wp_error.
    """
    final_md = (state.get("final_article") or "").strip()
    if not final_md:
        return {"status": "error", "messages": [HumanMessage(content="No final_article to publish")]}

    # Title from first line (strip '#')
    first_line = final_md.split("\n", 1)[0].lstrip("# ").strip()
    title = (first_line or "Untitled").strip()[:200]

    base_prompt = (state.get("image_prompt") or f"Editorial blog imagery for: {title}. Clean, modern, tech-journal style, no text overlays.").strip()

    # Debug the exact endpoints once (useful if 404 ever appears)
    base = _wp_base_url()
    print(f"[wp] base={base} posts_url={base + '/wp-json/wp/v2/posts'} media_url={base + '/wp-json/wp/v2/media'}", flush=True)

    try:
        # -------- 1) Featured (hero) image --------
        hero_b64 = _gen_image_b64(base_prompt + " — wide hero image, aesthetic, editorial, no text.", "1536x1024")
        hero_id, hero_src = _upload_media(hero_b64, "hero.png")

        # -------- 2) Two inline images --------
        inline_prompts = [
            base_prompt + " — square illustrative detail #1, minimal, no text.",
            base_prompt + " — square illustrative detail #2, minimal, no text."
        ]
        inline_urls: List[str] = []
        for i, p in enumerate(inline_prompts, start=1):
            b64 = _gen_image_b64(p, "1024x1024")
            _, src = _upload_media(b64, f"inline{i}.png")
            inline_urls.append(src)

        # -------- 3) Build final content: hero + markdown + inline blocks --------
        body_with_inline = _insert_inline_images(final_md, inline_urls)
        hero_html = f'<figure class="wp-block-image"><img src="{hero_src}" alt=""/></figure>\n\n'
        content_html = hero_html + body_with_inline

        # -------- 4) Create post with featured --------
        post = _create_post(title, content_html, featured_media_id=hero_id)

        print("✅ Article with featured + 2 inline images published to WordPress!", flush=True)
        return {
            "status": "published",
            "post_id": post.get("id"),
            "post_link": post.get("link"),
            "featured_media_id": hero_id,
            "messages": [HumanMessage(content="Published with featured + 2 inline images")],
        }

    except Exception as e:
        # strict: any failure (image gen/upload or post create) → error (no publish)
        print(f"⚠️ WordPress image/post error: {e}", flush=True)
        return {"status": "wp_error", "messages": [HumanMessage(content=f"WP error: {e}")]}
