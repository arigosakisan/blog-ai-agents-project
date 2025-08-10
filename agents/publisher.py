# agents/publisher.py
import os
import base64
import requests
from langchain_core.messages import HumanMessage

# ---------- OpenAI Images ----------
try:
    # OpenAI SDK v1.x
    import openai
    client = openai.OpenAI()
except Exception:
    client = None  # ako SDK nije dostupan, preskoči slike

# ---------- Config ----------
# Postavi u Render env:
# WORDPRESS_URL=https://api.trendsqueeze.com
# WORDPRESS_USERNAME=<wp user>
# WORDPRESS_PASSWORD=<wp application password>
# (opciono) IMAGE_ENABLED=true|false
# (opciono) WP_USER_AGENT=trendsqueeze-agent/1.0 (+https://trendsqueeze.com)

IMAGE_ENABLED = os.getenv("IMAGE_ENABLED", "true").lower() == "true"
UA = os.getenv("WP_USER_AGENT", "trendsqueeze-agent/1.0 (+https://trendsqueeze.com)")

def _wp_base_url() -> str:
    url = (os.getenv("WORDPRESS_URL") or "https://api.trendsqueeze.com").strip()
    if not url:
        raise RuntimeError("Missing WORDPRESS_URL")
    return url.rstrip("/")

def _wp_auth_headers() -> dict:
    user = os.getenv("WORDPRESS_USERNAME", "").strip()
    pwd = os.getenv("WORDPRESS_PASSWORD", "").strip()
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

# ---------- Image generation ----------
def _generate_image_b64(prompt: str | None) -> str | None:
    """
    Generate a wide header image via OpenAI Images API.
    Uses size 1536x1024. Returns base64 (no data: prefix).
    """
    if not IMAGE_ENABLED:
        return None
    if client is None:
        print("ℹ️ OpenAI client not available; skipping image.", flush=True)
        return None
    try:
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt or "Wide editorial blog header, clean, modern, technology theme",
            size="1536x1024",
            n=1,
        )
        return resp.data[0].b64_json
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}", flush=True)
        return None

def _upload_featured_image_to_wp(image_b64: str, filename: str = "header.png") -> tuple[int, str]:
    """
    Upload PNG to WordPress Media Library.
    Returns: (media_id, source_url)
    """
    media_url = _wp_base_url() + "/wp-json/wp/v2/media"
    binary = base64.b64decode(image_b64)
    r = requests.post(media_url, headers=_headers_media(filename), data=bytearray(binary), timeout=90)
    try:
        r.raise_for_status()
    except Exception as e:
        snippet = (r.text or "")[:300]
        raise RuntimeError(f"WP media upload failed: {r.status_code} {snippet}") from e

    j = r.json()
    media_id = j.get("id")
    source_url = j.get("source_url")
    if not media_id or not source_url:
        raise RuntimeError(f"WP media upload malformed response: {j}")
    return media_id, source_url

def _create_wp_post(title: str, content_html: str, featured_media_id: int | None = None) -> dict:
    posts_url = _wp_base_url() + "/wp-json/wp/v2/posts"
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",  # promeni u "draft" ako želiš da ručno pregledaš
    }
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    r = requests.post(posts_url, json=payload, headers=_headers_json(), timeout=90)
    if r.status_code == 201:
        return r.json()
    raise RuntimeError(f"WP post create failed: {r.status_code} {(r.text or '')[:300]}")

# ---------- Publisher node ----------
def publisher_node(state: dict) -> dict:
    """
    Input state:
      - final_article (Markdown as string)
      - image_prompt (optional)
    Output state keys:
      - status: "published" | "wp_error" | "error"
      - post_id, post_link, featured_media_id (optional)
    """
    final_article = (state.get("final_article") or "").strip()
    if not final_article:
        return {"status": "error", "messages": [HumanMessage(content="No final_article to publish")]}

    # Title = first line (strip '#')
    first_line = final_article.split("\n", 1)[0].lstrip("# ").strip()
    title = (first_line or "Untitled")[:200]

    # Try hero image (non-blocking)
    featured_id = None
    featured_src = None
    img_b64 = _generate_image_b64(state.get("image_prompt"))
    if img_b64:
        try:
            featured_id, featured_src = _upload_featured_image_to_wp(img_b64, "header.png")
        except Exception as e:
            print(f"⚠️ WP image upload failed: {e}", flush=True)

    # Compose content (WP accepts HTML; Markdown je OK, WP ga prikaže, ali ubacujemo <figure> za hero)
    content_body = final_article
    if featured_src:
        hero = f'<figure class="wp-block-image"><img src="{featured_src}" alt=""/></figure>\n\n'
        content_body = hero + content_body

    try:
        post = _create_wp_post(title, content_body, featured_media_id=featured_id)
        print("✅ Article published to WordPress!", flush=True)
        return {
            "status": "published",
            "post_id": post.get("id"),
            "post_link": post.get("link"),
            "featured_media_id": featured_id,
            "messages": [HumanMessage(content="Published to WordPress")],
        }
    except Exception as e:
        # tipično: 403 (ako nisi na api.* ili plugin/firewall blokira)
        print(f"⚠️ WordPress error: {e}", flush=True)
        return {"status": "wp_error", "messages": [HumanMessage(content=f"WP error: {e}")]}
