"""
News Scraper - Fetch articles from RSS feeds + BrightData fallback
"""
import feedparser
import requests
import re
import os
from datetime import datetime, timezone
from calendar import timegm
from database import insert_article
from config import NEWS_SOURCES, MAX_ARTICLES_PER_SOURCE, INTL_KEYWORD_FILTER

# Optional proxy config. Set BRIGHTDATA_PROXY_URL or leave empty for direct fetch.
_proxy_url = os.getenv("BRIGHTDATA_PROXY_URL", "")
BRIGHTDATA_PROXY = {"http": _proxy_url, "https": _proxy_url} if _proxy_url else None

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def parse_date(entry):
    """Extract published date from RSS entry"""
    for field in ['published_parsed', 'updated_parsed']:
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                pass
    return datetime.now(timezone.utc)


def clean_html(text):
    """Strip HTML tags from summary"""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:500]


def matches_indonesia(title, summary):
    """Check if intl article is about Indonesia/Prabowo/etc."""
    blob = f"{title} {summary}".lower()
    return any(kw.lower() in blob for kw in INTL_KEYWORD_FILTER)


def scrape_rss(source):
    """Scrape articles from RSS feed"""
    articles = []
    use_proxy = source.get("use_proxy", False)
    is_intl = source.get("intl", False)

    try:
        feed = None
        # If forced-proxy, fetch with proxy first
        if use_proxy:
            try:
                resp = requests.get(source["url"], headers=UA_HEADERS, proxies=BRIGHTDATA_PROXY, verify=False, timeout=30)
                feed = feedparser.parse(resp.text)
            except Exception as e:
                print(f"  Proxy fetch failed for {source['name']}: {e}")

        # Try direct (with UA for intl sources)
        if feed is None or (feed.bozo and not feed.entries):
            try:
                if is_intl:
                    resp = requests.get(source["url"], headers=UA_HEADERS, timeout=20)
                    feed = feedparser.parse(resp.text)
                else:
                    feed = feedparser.parse(source["url"])
            except Exception as e:
                print(f"  Direct fetch failed for {source['name']}: {e}")

        # Fallback BrightData
        if feed is None or (feed.bozo and not feed.entries):
            print(f"  Trying BrightData for {source['name']}...")
            try:
                resp = requests.get(source["url"], headers=UA_HEADERS, proxies=BRIGHTDATA_PROXY, verify=False, timeout=30)
                feed = feedparser.parse(resp.text)
            except Exception as e:
                print(f"  BrightData failed for {source['name']}: {e}")
                return articles

        if not feed or not feed.entries:
            print(f"  No entries for {source['name']}")
            return articles

        # For intl sources, scan more entries (since most won't match Indonesia filter)
        scan_limit = 50 if is_intl else MAX_ARTICLES_PER_SOURCE
        kept = 0

        for entry in feed.entries[:scan_limit]:
            if kept >= MAX_ARTICLES_PER_SOURCE:
                break
            title = entry.get('title', '').strip()
            url = entry.get('link', '').strip()
            summary = clean_html(entry.get('summary', '') or entry.get('description', ''))
            published = parse_date(entry)

            if not (title and url):
                continue

            # Filter intl articles to Indonesia-related only
            if is_intl and not matches_indonesia(title, summary):
                continue

            articles.append({
                "title": title,
                "url": url,
                "source": source["name"],
                "summary": summary,
                "published_at": published.isoformat(),
            })
            kept += 1
    except Exception as e:
        print(f"  Error scraping {source['name']}: {e}")

    return articles


def scrape_all():
    """Scrape all configured news sources"""
    total = 0
    new = 0
    
    for source in NEWS_SOURCES:
        print(f"Scraping {source['name']}...")
        
        if source["type"] == "rss":
            articles = scrape_rss(source)
        else:
            continue
        
        for article in articles:
            inserted = insert_article(
                title=article["title"],
                url=article["url"],
                source=article["source"],
                summary=article["summary"],
                published_at=article["published_at"],
            )
            total += 1
            if inserted:
                new += 1
        
        print(f"  → {len(articles)} fetched, {new} new")
    
    print(f"\nTotal: {total} articles processed, {new} new inserted")
    return {"total": total, "new": new}


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_all()
