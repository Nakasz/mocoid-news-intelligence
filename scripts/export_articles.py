#!/usr/bin/env python3
"""Export top 100 ranked articles to articles.json with OG images + LLM bullet points."""
from database import get_db
import requests
from bs4 import BeautifulSoup
import json
import re
import concurrent.futures
from datetime import datetime, timezone, timedelta

# Only show articles published within MAX_AGE_HOURS — older articles get pruned
# even if their score is high. User wants "berita terbaru, jangan yang lama".
MAX_AGE_HOURS = 36

cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)).isoformat()

conn = get_db()

# Query more articles so both ID and Inter tabs can fill 100
articles = conn.execute('''
    SELECT title, url, source, published_at, final_score
    FROM articles
    WHERE final_score IS NOT NULL
      AND published_at IS NOT NULL
      AND published_at >= ?
    ORDER BY final_score DESC LIMIT 250
''', (cutoff,)).fetchall()
conn.close()

print(f'Cutoff: {cutoff} ({MAX_AGE_HOURS}h)')
print(f'Fetched {len(articles)} articles')

# Split by source: Indonesian vs International
INTL_SOURCES = {
    'Bloomberg', 'Bloomberg Markets', 'Bloomberg Politics',
    'Japan Times', 'The Economist', 'The Economist Asia',
    'Straits Times', 'Straits Times Asia', 'Nikkei Asia',
}

# For intl articles, include ALL (no cutoff — user-curated international news)
# Query ALL intl articles regardless of age or score
conn2 = get_db()
intl_all_articles = conn2.execute('''
    SELECT title, url, source, published_at, final_score
    FROM articles
    WHERE source IN ('Bloomberg','Bloomberg Markets','Bloomberg Politics',
                     'Japan Times','The Economist','The Economist Asia',
                     'Straits Times','Straits Times Asia','Nikkei Asia')
      AND published_at IS NOT NULL
    ORDER BY published_at DESC LIMIT 100
''').fetchall()
conn2.close()

raw_id = []
raw_intl = []
seen_urls = set()
for a in articles:
    entry = {'title': a[0], 'url': a[1], 'source': a[2], 'published': a[3], 'score': round(a[4], 2)}
    seen_urls.add(a[1])
    if a[2] in INTL_SOURCES:
        raw_intl.append(entry)
    else:
        raw_id.append(entry)

for a in intl_all_articles:
    if a[1] not in seen_urls:
        entry = {'title': a[0], 'url': a[1], 'source': a[2], 'published': a[3], 'score': round(a[4], 2)}
        seen_urls.add(a[1])
        if a[2] in INTL_SOURCES:
            raw_intl.append(entry)

# Cap at 100 each
data_id = raw_id[:100]
data_intl = raw_intl[:100]
print(f'ID: {len(data_id)} articles, Inter: {len(data_intl)} articles')

# Merge for OG image + bullet processing (deduplicate work)
data_all = data_id + data_intl

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch_og(article):
    try:
        r = requests.get(article['url'], headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        og = soup.find('meta', property='og:image')
        return og['content'] if og else None
    except Exception:
        return None


with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
    images = list(ex.map(fetch_og, data_all))

for i, img in enumerate(images):
    if img:
        data_all[i]['image'] = img

print(f'OG images: {sum(1 for d in data_all if "image" in d)}/{len(data_all)}')


# Bad phrases that indicate leaked reasoning (English meta-commentary instead of Indonesian bullets)
BAD_PHRASES = [
    'user wants', 'summarize', 'bullet point', 'max 12 word', 'i need to',
    'let me ', 'as an ai', 'in 2-3', '12 words', "i'll provide", 'i should',
    'okay,', 'first,', 'the key', 'main point', 'the article', 'the news',
    'key points', 'news article', 'news headline', 'i need',
]


def clean_bullets(content: str):
    # Strip <think>...</think> blocks (MiMo leaks reasoning even when enable_thinking=false)
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<think>.*', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)

    lines = []
    for raw in content.strip().split('\n'):
        line = raw.strip()
        if not line:
            continue
        # strip markdown emphasis
        clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        clean = re.sub(r'\*([^*]+)\*', r'\1', clean)
        # strip bullet/numbered list markers
        clean = re.sub(r'^[•\-\*\d\.]+\s*', '', clean).strip()
        if not clean or len(clean) <= 5 or clean.startswith('#'):
            continue
        cl = clean.lower()
        if any(bp in cl for bp in BAD_PHRASES):
            continue
        # require at least one Indonesian-ish character context (skip pure English meta lines)
        # heuristic: drop lines that are clearly English explanatory prose
        if cl.startswith(('the ', 'this ', 'these ', 'i ', "i'm", "i'll", "let's", 'we ', 'they ')):
            continue
        lines.append(clean)
    return lines[:3] if lines else None


def get_bullets(a, retries=3):
    """Try up to `retries` times. MiMo sometimes returns empty/think-only content under load."""
    for attempt in range(retries):
        try:
            resp = requests.post('http://localhost:19911/v1/chat/completions', json={
                'model': 'mimo-v2.5-pro',
                'messages': [
                    {'role': 'system', 'content': 'Kamu asisten berita berbahasa Indonesia. Jawab HANYA dengan 2-3 bullet point dalam Bahasa Indonesia. Format tiap baris: • [isi max 12 kata]. Tanpa header, tanpa pengantar, tanpa penutup, tanpa think block, tanpa Bahasa Inggris.'},
                    {'role': 'user', 'content': f'Poin penting berita: "{a["title"]}" ({a["source"]})'}
                ],
                'max_tokens': 250,
                'temperature': 0.1,
                'enable_thinking': False
            }, timeout=90)
            msg = resp.json()['choices'][0]['message']
            content = msg.get('content') or ''
            bullets = clean_bullets(content)
            if bullets:
                return bullets
        except Exception:
            pass
    return None


with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
    bullets = list(ex.map(get_bullets, data_all))

for i, b in enumerate(bullets):
    if b:
        data_all[i]['points'] = b

print(f'Bullet points: {sum(1 for d in data_all if "points" in d)}/{len(data_all)}')

# Write split files — data_all has OG images + bullets assigned, split back
data_id = [d for d in data_all if d['source'] not in INTL_SOURCES][:100]
data_intl = [d for d in data_all if d['source'] in INTL_SOURCES][:100]

with open('vercel-deploy/articles.json', 'w') as f:
    json.dump(data_id, f, ensure_ascii=False)
with open('vercel-deploy/articles_inter.json', 'w') as f:
    json.dump(data_intl, f, ensure_ascii=False)
print(f'Exported articles.json ({len(data_id)}) + articles_inter.json ({len(data_intl)})')
