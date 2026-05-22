"""
News Recommender - Web UI + API Server
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from datetime import datetime

from database import init_db, get_top_articles, get_article_count
from scraper import scrape_all
from ranker import run_full_ranking
from config import HOST, PORT

app = FastAPI(title="News Recommender", version="1.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/articles")
def api_articles(limit: int = 50, hours: int = 48):
    """Get ranked articles"""
    articles = get_top_articles(limit=limit, hours=hours)
    return {"articles": articles, "count": len(articles)}


@app.post("/api/scrape")
def api_scrape():
    """Trigger scraping"""
    result = scrape_all()
    return {"status": "ok", **result}


@app.post("/api/rank")
def api_rank():
    """Trigger ranking"""
    run_full_ranking()
    return {"status": "ok"}


@app.post("/api/refresh")
def api_refresh():
    """Scrape + rank in one call"""
    scrape_result = scrape_all()
    run_full_ranking()
    articles = get_top_articles(limit=30)
    return {"status": "ok", "scrape": scrape_result, "top_articles": len(articles)}


@app.get("/api/stats")
def api_stats():
    """Pipeline stats"""
    return {
        "total_articles": get_article_count(),
        "last_refresh": datetime.now().isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_TEMPLATE


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Recommender — Politik Indonesia</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            min-height: 100vh;
        }
        .container { max-width: 800px; margin: 0 auto; padding: 20px; }
        
        header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 0; border-bottom: 1px solid #222;
            margin-bottom: 24px;
        }
        h1 { font-size: 1.4rem; color: #fff; }
        .subtitle { color: #888; font-size: 0.85rem; margin-top: 4px; }
        
        .controls { display: flex; gap: 10px; }
        .btn {
            padding: 8px 16px; border: 1px solid #333; border-radius: 6px;
            background: #1a1a1a; color: #ccc; cursor: pointer;
            font-size: 0.85rem; transition: all 0.2s;
        }
        .btn:hover { background: #2a2a2a; border-color: #555; color: #fff; }
        .btn.loading { opacity: 0.5; pointer-events: none; }
        .btn-primary { background: #1d4ed8; border-color: #1d4ed8; color: #fff; }
        .btn-primary:hover { background: #2563eb; }
        
        .stats {
            display: flex; gap: 20px; margin-bottom: 20px;
            padding: 12px 16px; background: #1a1a1a; border-radius: 8px;
            font-size: 0.8rem; color: #888;
        }
        .stats span { color: #fff; font-weight: 600; }
        
        .article {
            padding: 16px 0; border-bottom: 1px solid #1a1a1a;
            transition: background 0.2s;
        }
        .article:hover { background: #141414; margin: 0 -12px; padding: 16px 12px; border-radius: 8px; }
        
        .article-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
        .article-title {
            font-size: 1rem; font-weight: 500; color: #fff;
            text-decoration: none; line-height: 1.4;
        }
        .article-title:hover { color: #60a5fa; }
        
        .score-badge {
            flex-shrink: 0; padding: 3px 8px; border-radius: 4px;
            font-size: 0.75rem; font-weight: 600;
        }
        .score-high { background: #166534; color: #4ade80; }
        .score-mid { background: #854d0e; color: #fbbf24; }
        .score-low { background: #333; color: #888; }
        
        .article-meta {
            display: flex; gap: 12px; margin-top: 6px;
            font-size: 0.8rem; color: #666;
        }
        .source { color: #60a5fa; }
        .keywords { color: #a78bfa; }
        
        .article-summary {
            margin-top: 8px; font-size: 0.85rem; color: #999;
            line-height: 1.5; display: -webkit-box;
            -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        
        .empty { text-align: center; padding: 60px 20px; color: #666; }
        .empty p { margin-top: 8px; }
        
        .loading-bar {
            position: fixed; top: 0; left: 0; width: 100%; height: 3px;
            background: linear-gradient(90deg, #1d4ed8, #60a5fa, #1d4ed8);
            background-size: 200% 100%; animation: loading 1.5s infinite;
            display: none;
        }
        .loading-bar.active { display: block; }
        @keyframes loading { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    </style>
</head>
<body>
    <div class="loading-bar" id="loadingBar"></div>
    <div class="container">
        <header>
            <div>
                <h1>📰 News Recommender</h1>
                <div class="subtitle">Politik Indonesia • Ranked by relevance</div>
            </div>
            <div class="controls">
                <button class="btn btn-primary" onclick="refresh()">🔄 Refresh</button>
            </div>
        </header>
        
        <div class="stats" id="stats">
            <div>Articles: <span id="statCount">-</span></div>
            <div>Last update: <span id="statTime">-</span></div>
        </div>
        
        <div id="articles">
            <div class="empty">
                <h3>Belum ada artikel</h3>
                <p>Klik Refresh untuk mulai scraping</p>
            </div>
        </div>
    </div>

    <script>
        async function loadArticles() {
            try {
                const resp = await fetch('/api/articles?limit=50&hours=72');
                const data = await resp.json();
                renderArticles(data.articles);
                document.getElementById('statCount').textContent = data.count;
                document.getElementById('statTime').textContent = new Date().toLocaleTimeString('id-ID');
            } catch(e) {
                console.error(e);
            }
        }
        
        async function refresh() {
            const bar = document.getElementById('loadingBar');
            bar.classList.add('active');
            try {
                await fetch('/api/refresh', {method: 'POST'});
                await loadArticles();
            } catch(e) {
                console.error(e);
            }
            bar.classList.remove('active');
        }
        
        function scoreClass(score) {
            if (score >= 3) return 'score-high';
            if (score >= 1) return 'score-mid';
            return 'score-low';
        }
        
        function renderArticles(articles) {
            const container = document.getElementById('articles');
            if (!articles.length) {
                container.innerHTML = '<div class="empty"><h3>Belum ada artikel</h3><p>Klik Refresh untuk mulai scraping</p></div>';
                return;
            }
            
            container.innerHTML = articles.map(a => `
                <div class="article">
                    <div class="article-header">
                        <a href="${a.url}" target="_blank" class="article-title">${a.title}</a>
                        <div class="score-badge ${scoreClass(a.final_score)}">${a.final_score.toFixed(1)}</div>
                    </div>
                    <div class="article-meta">
                        <span class="source">${a.source}</span>
                        <span>${timeAgo(a.published_at)}</span>
                        ${a.keywords_matched ? `<span class="keywords">${a.keywords_matched.split(',').slice(0,3).join(', ')}</span>` : ''}
                    </div>
                    ${a.summary ? `<div class="article-summary">${a.summary}</div>` : ''}
                </div>
            `).join('');
        }
        
        function timeAgo(dateStr) {
            if (!dateStr) return '';
            const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
            if (diff < 3600) return Math.floor(diff/60) + ' menit lalu';
            if (diff < 86400) return Math.floor(diff/3600) + ' jam lalu';
            return Math.floor(diff/86400) + ' hari lalu';
        }
        
        // Load on page open
        loadArticles();
    </script>
</body>
</html>"""


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
