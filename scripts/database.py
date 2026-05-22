"""
SQLite database for storing scraped articles
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "news.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            source TEXT NOT NULL,
            summary TEXT,
            published_at TIMESTAMP,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            heuristic_score REAL DEFAULT 0,
            llm_score REAL DEFAULT 0,
            final_score REAL DEFAULT 0,
            keywords_matched TEXT,
            is_reranked INTEGER DEFAULT 0
        );
        
        CREATE INDEX IF NOT EXISTS idx_articles_final_score ON articles(final_score DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);
    """)
    conn.commit()
    conn.close()


def insert_article(title, url, source, summary=None, published_at=None):
    conn = get_db()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO articles (title, url, source, summary, published_at)
               VALUES (?, ?, ?, ?, ?)""",
            (title, url, source, summary, published_at)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def update_scores(article_id, heuristic_score=None, llm_score=None, final_score=None, keywords_matched=None):
    conn = get_db()
    updates = []
    params = []
    
    if heuristic_score is not None:
        updates.append("heuristic_score = ?")
        params.append(heuristic_score)
    if llm_score is not None:
        updates.append("llm_score = ?")
        params.append(llm_score)
        updates.append("is_reranked = 1")
    if final_score is not None:
        updates.append("final_score = ?")
        params.append(final_score)
    if keywords_matched is not None:
        updates.append("keywords_matched = ?")
        params.append(keywords_matched)
    
    if updates:
        params.append(article_id)
        conn.execute(f"UPDATE articles SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
    conn.close()


def get_top_articles(limit=50, hours=48):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM articles 
           WHERE published_at > datetime('now', ?) 
           ORDER BY final_score DESC 
           LIMIT ?""",
        (f"-{hours} hours", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unscored_articles():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM articles WHERE heuristic_score = 0 ORDER BY scraped_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_top_for_rerank(limit=20):
    conn = get_db()
    rows = conn.execute(
        """SELECT * FROM articles 
           WHERE is_reranked = 0 AND heuristic_score > 0
           ORDER BY heuristic_score DESC 
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_article_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    return count


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
