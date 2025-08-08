# agents/writer.py
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

def writer_node(state):
    llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

    # Tvoj prompt – odličan za prirodan stil
    prompt = f"""
You are a content writer helping me create a blog post for my WordPress site.

Here’s your task:
Using the following Reddit post as inspiration, write a full blog article. The tone should be friendly, personal, and natural — like you're talking to a curious friend over coffee.

---
🔹 Reddit Post:
Title: {state['original_post']['title']}
Description: {state['original_post']['summary']}
---

🎯 Goal:
Turn this into an engaging blog post that would perform well on Medium or similar platforms. Add a catchy title and optional subheading.

📌 Write using these style rules:

* **Use clear, everyday language:** Simple words. Short sentences. Write like a human, not a robot.
* **No clichés or hype words:** Avoid terms like “game-changer” or “revolutionize.” Just be real.
* **Be direct:** Get to the point fast. Cut the fluff.
* **Use a natural voice:** It's okay to start sentences with "But" or "So." Write like you speak.
* **Focus on value:** Don’t oversell. Instead, explain the benefit honestly.
* **Be human:** Don’t fake excitement. Just share what’s interesting, surprising, or useful.
* **Light structure:** Use short paragraphs, subheadings, and maybe a few bullet points.
* **Emotion + story welcome:** Share small stories or examples if it helps explain the point.
* **Title must be catchy and relevant.**

⛔ Avoid:
- Robotic or overly formal tone
- Long, dense paragraphs
- Generic summaries or filler content

✅ Do:
- Write in first person if it makes sense
- Use contractions ("I'm", "it's", etc.)
- Keep it scannable and interesting

Now go ahead and write the blog post. Start with a headline, then dive right into the story or explanation.

At the end, add:
[IMAGE_PROMPT]: A detailed description for a wide-format AI-generated image (1792x1024) that captures the essence of the article.
"""

    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content

    if "[IMAGE_PROMPT]:" in content:
        article, img_prompt = content.split("[IMAGE_PROMPT]:", 1)
    else:
        article, img_prompt = content, "A wide, cinematic view representing the core idea of the article, 1792x1024"

    return {
        "draft_article": article.strip(),
        "image_prompt": img_prompt.strip(),
        "messages": [HumanMessage(content="Writer: article drafted in natural tone")],
        "status": "written"
    }