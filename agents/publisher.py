import os
import base64
import requests
from langchain_core.messages import HumanMessage

# OpenAI Python SDK v1.x
import openai
client = openai.OpenAI()

def _wp_auth_headers():
    user = os.getenv("WORDPRESS_USERNAME")
    pwd  = os.getenv("WORDPRESS_PASSWORD")
    if not user or not pwd:
        raise RuntimeError("Missing WORDPRESS_USERNAME or WORDPRESS_PASSWORD")
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return {"Authorization": f"Basic {token}"}

def _wp_base_url():
    url = os.getenv("WORDPRESS_URL")
    if not url:
        raise RuntimeError("Missing WORDPRESS_URL")
    return url.rstrip("/")

def _generate_image_b64(prompt: str | None) -> str | None:
    try:
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt or "Wide blog header image, 1792x1024, clean, modern, editorial",
            size="1792x1024",
            n=1,
            response_format="b64_json",
        )
        return resp.data[0].b64_json
    except Exception as e:
        print(f"❌ Image generation failed: {e}", flush=True)
        return None

def _upload_featured_image_to_wp(image_b64: str, filename: str = "header.png") -> tuple[int, str]:
    media_url = _wp_base_url() + "/wp-json/wp/v2/media"
    headers = _wp_auth_headers()
    binary = base64.b64decode(image_b64)

    up_headers = {
        **headers,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/png",
    }
    r = requests.post(media_url, headers=up_headers, data=bytearray(binary), timeout=60)
    try:
        r.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"WP media upload failed: {r.status_code} {r.text}") from e

    j = r.json()
    media_id = j.get("id")
    source_url = j.get("source_url")
    if not media_id or not source_url:
        raise RuntimeError(f"WP media upload malformed response: {j}")
    return media_id, source_url

def publisher_node(state: dict) -> dict:
    final_article = (state.get("final_article") or "").strip()
    if not final_article:
        return {
            "status": "error",
            "messages": [HumanMessage(content="No final_article to publish")]
        }

    # Title = prva linija bez # i ograničiti na 200 char
    first_line = final_article.split("\n", 1)[0].lstrip("# ").strip() or "Untitled"
    title = first_line[:200]

    # Slika (opciono)
    featured_id = None
    featured_src = None
    img_b64 = _generate_image_b64(state.get("image_prompt"))
    if img_b64:
        try:
            featured_id, featured_src = _upload_featured_image_to_wp(img_b64, "header.png")
        except Exception as e:
            print(f"❌ WP image upload failed: {e}", flush=True)

    content_body = final_article
    if featured_src:
        hero = f'<figure class="wp-block-image"><img src="{featured_src}" alt=""/></figure>\n\n'
        content_body = hero + content_body

    posts_url = _wp_base_url() + "/wp-json/wp/v2/posts"
    headers = {**_wp_auth_headers(), "Content-Type": "application/json"}

    payload = {
        "title": title,
        "content": content_body,
        "status": "publish",  # ili "draft" za test
    }
    if featured_id:
        payload["featured_media"] = featured_id

    try:
        r = requests.post(posts_url, json=payload, headers=headers, timeout=60)
        if r.status_code == 201:
            post = r.json()
            print("✅ Article published to WordPress!", flush=True)
            return {
                "status": "published",
                "post_id": post.get("id"),
                "post_link": post.get("link"),
                "featured_media_id": featured_id,
                "messages": [HumanMessage(content="Published to WordPress")],
            }
        else:
            print(f"⚠️ WordPress error {r.status_code}: {r.text}", flush=True)
            return {
                "status": "wp_error",
                "messages": [HumanMessage(content=f"WP error {r.status_code}")]
            }
    except Exception as e:
        print(f"❌ Failed to connect to WordPress: {e}", flush=True)
        return {
            "status": "error",
            "messages": [HumanMessage(content="WP connection failed")]
        }
