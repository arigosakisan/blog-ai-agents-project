# 🤖 AI-Powered Blog Content Engine

> Automated content pipeline that monitors Reddit for trending topics, generates blog articles using AI, and publishes directly to WordPress — no manual intervention required.

## 📋 Project Overview

This project demonstrates **end-to-end AI workflow automation** — a practical example of how AI tools can be integrated into business processes to eliminate repetitive tasks and deliver consistent output.

**The Problem:** Content creation is time-consuming. Identifying trending topics, researching them, writing articles, and publishing — each step requires manual effort and hours of work.

**The Solution:** A Python-based automated pipeline that handles the entire content lifecycle:

```
Reddit Monitoring → Topic Selection → AI Content Generation → WordPress Publishing
```

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐     ┌──────────────┐
│  Reddit API     │────▶│  Topic Analysis  │────▶│  AI Generator   │────▶│  WordPress   │
│  (Data Source)  │     │  & Filtering     │     │  (Article Gen)  │     │  (Publishing)│
└─────────────────┘     └──────────────────┘     └─────────────────┘     └──────────────┘
       │                        │                        │                       │
   Trending posts       Relevance scoring        Content creation        Auto-publish
   from subreddits      & deduplication          with AI models          with formatting
```

## ⚡ Key Features

- **Automated Reddit Monitoring** — Tracks trending posts across configured subreddits using Reddit API
- **Intelligent Topic Selection** — Filters and scores topics based on relevance, engagement, and freshness
- **AI-Powered Article Generation** — Leverages AI language models to produce well-structured blog articles
- **WordPress Auto-Publishing** — Publishes finished articles directly via WordPress REST API
- **Configurable Pipeline** — Easily adjust subreddits, publishing frequency, content style, and AI parameters

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.x |
| Data Source | Reddit API (PRAW) |
| AI Engine | OpenAI / Claude API |
| Publishing | WordPress REST API |
| Automation | Scheduled execution |
| Depoy | Render |
| Tracking | LangGraph |

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Reddit API credentials ([create app here](https://www.reddit.com/prefs/apps))
- AI API key (OpenAI or Anthropic)
- WordPress site with REST API enabled

### Installation

```bash
# Clone the repository
git clone https://github.com/arigosakisan/blog-ai-agents-project.git
cd blog-ai-agents-project

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Update the configuration file with your preferences:

```python
# Subreddits to monitor
SUBREDDITS = ["technology", "science", "business", "AI"]

# Publishing settings
POST_FREQUENCY = "daily"
CONTENT_LENGTH = "medium"  # short | medium | long
```

### Usage

```bash
# Run the full pipeline
python main.py

# Monitor only (no publishing)
python main.py --dry-run

# Generate article for specific topic
python main.py --topic "AI in project management"
```

## 📊 How It Works

1. **Monitor** — The system connects to Reddit API and pulls top/trending posts from configured subreddits
2. **Analyze** — Posts are scored based on engagement metrics (upvotes, comments, awards) and filtered for relevance
3. **Generate** — The highest-scoring topic is sent to the AI model with a structured prompt to generate a complete blog article
4. **Publish** — The formatted article is pushed to WordPress via REST API with proper categories and tags
5. **Log** — Each run is logged to prevent duplicate topics and track publishing history
6. **Deploy** - Code was deployed over https://render.com/
7. **Tracking** - The whole process was tracked over https://www.langchain.com/langgraph

## 💡 Use Cases

- **Content Marketing Automation** — Maintain a consistent blog publishing schedule without manual writing
- **Trend Monitoring** — Stay on top of industry trends by automatically tracking relevant subreddits
- **AI Integration Demo** — Practical example of integrating AI APIs into a business workflow
- **Rapid Prototyping** — Template for building similar automation pipelines for other content sources

## 🔮 Future Improvements

- [ ] Multi-platform publishing (Medium, LinkedIn, DEV.to)
- [ ] Image generation for article thumbnails
- [ ] SEO optimization module
- [ ] Analytics dashboard for published content performance
- [ ] Multi-language support

## 📝 Lessons Learned

This project reinforced several key insights about AI-powered automation:

- **AI works best with structure** — Clear prompts and defined output formats produce dramatically better results than open-ended requests
- **Human oversight matters** — The `--dry-run` mode exists because automated content still benefits from human review before publishing
- **API integration is a superpower** — Connecting multiple APIs (Reddit + AI + WordPress) creates value far beyond what any single tool provides

## 👤 Author

**Bojan Milosavljevic**
- LinkedIn: [linkedin.com/in/bojan-milosavljevic-pm](https://linkedin.com/in/bojan-milosavljevic-pm)
- GitHub: [@arigosakisan](https://github.com/arigosakisan)

---

*Built with Python and AI-powered tools — demonstrating practical workflow automation and AI integration.*
