# agents/publisher.py
import os
import base64
import requests
from langchain_core.messages import HumanMessage
import openai

# OpenAI client (SDK v1.x)
client = openai.OpenAI()

# User-Agent za WP (podesivo preko env var)
UA = os.getenv("WP_USER_AGENT", "trendsqueeze-agent/1.0 (+https://trendsqueeze.com)")

def _wp_base_url() -> str:
    url = os.getenv("WORDPRESS_URL", "").strip()
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

def _generate_image_b64(prompt: str | None) -> str | None:
    """
    Generate a 1792x1024 header image using OpenAI Images API.
    Novi SDK vraća b64_json podrazumevano, ne prosleđujemo response_format.
    """
    try:
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt or "Wide blog header image, 1792x1024, clean, modern, editorial",
            size="1792x1024",
            n=1,
        )
        return resp.data[0].b64_json
    except Exception as e:
        print(f"❌ Image generation failed: {e}", flush=True)
        return None

def _upload_featured_image_to_wp(image_b64: str, filename: str = "header.png") -> tuple[int, str]:
    """
    Upload the PNG to WordPress media library.
    Returns: (media_id, source_url)
    """
    media_url = _wp_base_url() + "/wp-json/wp/v2/media"
    headers = {
        **_wp_auth_headers(),
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/png",
        "User-Agent": UA,
        "Accept": "application/json",
    }

    binary = base64.b64decode(image_b64)
    r = requests.post(media_url, headers=headers, data=bytearray(binary), timeout=90)
    try:
        r.raise_for_status()
    except Exception as e:
        # Cloudflare/WAF često vraća 403 sa HTML stranom
        raise RuntimeError(f"WP media upload failed: {r.status_code} {r.text[:300]}") from e

    j = r.json()
    media_id = j.get("id")
    source_url = j.get("source_url")
    if not media_id or not source_url:
        raise RuntimeError(f"WP media upload malformed response: {j}")
    return media_id, source_url

def _create_wp_post(title: str, content_html: str, featured_media_id: int | None = None) -> dict:
    posts_url = _wp_base_url() + "/wp-json/wp/v2/posts"
    headers = {
        **_wp_auth_headers(),
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Accept": "application/json",
    }
    payload = {
        "title": title,
        "content": content_html,
        "status": "publish",  # ako želiš draft: "draft"
    }
    if featured_media_id:
        payload["featured_media"] = featured_media_id

    r = requests.post(posts_url, json=payload, headers=headers, timeout=90)
    if r.status_code == 201:
        return r.json()
    raise RuntimeError(f"WP post create failed: {r.status_code} {r.text[:300]}")

def publisher_node(state: dict) -> dict:
    """
    Očekuje u state:
      - final_article (Markdown)
      - image_prompt (string, opciono)
    Vraća:
      - status, post_id, post_link, featured_media_id (opciono)
    """
    final_article = (state.get("final_article") or "").strip()
    if not final_article:
        return {"status": "error", "messages": [HumanMessage(content="No final_article to publish")]}

    # Title = prva linija bez '#'
    first_line = final_article.split("\n", 1)[0].lstrip("# ").strip() or "Untitled"
    title = first_line[:200]

    # Pokušaj generisanje hero slike (ne blokira objavu ako padne)
    featured_id = None
    featured_src = None
    img_b64 = _generate_image_b64(state.get("image_prompt"))
    if img_b64:
        try:
            featured_id, featured_src = _upload_featured_image_to_wp(img_b64, "header.png")
        except Exception as e:
            print(f"⚠️ WP image upload failed: {e}", flush=True)

    # Priprema HTML sadržaja (WP očekuje HTML; Markdown može proći jer WP editor parsira, ali hero ubacujemo kao <figure>)
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
        # Tipično: 403 od Cloudflare-a. Rešenje je WAF pravilo koje dopušta Render IP-ove na /wp-json.
        print(f"⚠️ WordPress error: {e}", flush=True)
        return {"status": "wp_error", "messages": [HumanMessage(content=f"WP error: {e}")]}
