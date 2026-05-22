# Mocoid News Intelligence

Mocoid is a lightweight news intelligence dashboard for monitoring Indonesian and international political, economic, and market-related headlines in one place.

Live site: https://mocoid.my.id

## Features

- **News ID**: Indonesian news feed focused on politics, public policy, economy, and national issues.
- **News Inter**: International coverage about Indonesia and regional/global economic signals.
- **Substack**: Curated long-form sources and analysis feeds.
- **LLM ranking**: Articles are first scored heuristically, then re-ranked with a MiMo/OpenAI-compatible LLM.
- **Read-state filtering**: Hide articles already marked as read.
- **Article pinning**: Save important stories for later review.
- **Static deployment**: Exported JSON + static frontend, deployed on Vercel.

## Pipeline

The scraping and ranking pipeline lives in `scripts/`:

- `scripts/scraper.py` — scrapes RSS feeds for Indonesian news and international Indonesia-related coverage.
- `scripts/ranker.py` — scores articles using keyword/recency heuristics, then re-ranks top candidates with an LLM.
- `scripts/export_articles.py` — exports ranked articles to JSON files consumed by the static frontend.
- `scripts/daily_update.sh` — daily automation: scrape → rank → export → deploy.
- `scripts/config.py` — source list, ranking weights, and LLM config.
- `scripts/database.py` — SQLite storage layer.
- `scripts/server.py` — optional local FastAPI server.

## Outputs

The frontend reads:

- `src/articles.json` — Indonesian news.
- `src/articles_inter.json` — international news filtered for Indonesia/Prabowo/ASEAN topics.
- `src/substack.json` — Substack/long-form feed.

## Schedule

Production VPS cron currently updates the pipeline daily. Recommended single daily update schedule:

```cron
0 18 * * * /home/ubuntu/news-recommender/daily_update.sh >> /home/ubuntu/news-recommender/cron.log 2>&1
```

## Local usage

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd scripts
python scraper.py
python -c "from ranker import run_full_ranking; run_full_ranking()"
python export_articles.py
```

Run frontend locally:

```bash
python3 -m http.server 3000 --directory src
```

## Environment variables

Never commit real tokens or proxy passwords.

```bash
export MIMO_BASE_URL="http://localhost:19911/v1"
export MIMO_MODEL="mimo-v2.5-pro"
export MIMO_API_KEY="your-llm-api-key"
export BRIGHTDATA_PROXY_URL="http://user:pass@host:port"   # optional
export VERCEL_TOKEN="your-vercel-token"                    # optional deploy step
```

## MiMo 100T angle

Mocoid demonstrates a practical information monitoring workflow: aggregate multi-source news, rank by relevance, re-rank with an LLM, and present a compact decision-support interface for Indonesia-focused political and market intelligence.
