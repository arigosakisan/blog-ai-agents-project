# agents/publisher.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
import openai
import requests
import base64
import os

def publisher_node(state):
    client = openai.OpenAI()

    # Generate wide image: 1792x1024 (best for blogs)
    try:
        image_response = client.images.generate(
            prompt=state['image_prompt'],
            size="1792x1024",  # Wide format
            n=1
        )
        image_url = image_response.data[0].url
    except Exception as e:
        print(f"❌ Image generation failed: {e}")
        image_url = None

    # WordPress publish
    wp_url = os.getenv("WORDPRESS_URL") + "/wp-json/wp/v2/posts"
    auth = base64.b64encode(
        f"{os.getenv('WORDPRESS_USERNAME')}:{os.getenv('WORDPRESS_PASSWORD')}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/json"
    }

    data = {
        "title": state['final_article'].split('\n')[0][:200],
        "content": state['final_article'],
        "status": "publish",
        "categories": [1],
        "tags": [10]
    }

    try:
        r = requests.post(wp_url, json=data, headers=headers)
        if r.status_code == 201:
            print("✅ Article published to WordPress!")
        else:
            print(f"⚠️ WordPress error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed to connect to WordPress: {str(e)}")

    return {
        "image_url": image_url,
        "status": "published",
        "messages": [HumanMessage(content="Published to WordPress")]
    }