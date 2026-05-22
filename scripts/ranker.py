"""
Ranking Engine - 2 layers:
Layer 1: Heuristic scoring (keyword match × recency × source weight)
Layer 2: LLM re-rank top candidates via MiMo
"""
import json
import re
import requests
from datetime import datetime, timezone
from database import get_unscored_articles, get_top_for_rerank, update_scores
from config import INTEREST_KEYWORDS, NEWS_SOURCES, RECENCY_DECAY_HOURS, LLM_CONFIG, TOP_CANDIDATES_FOR_RERANK


def get_source_weight(source_name):
    """Get source weight from config"""
    for s in NEWS_SOURCES:
        if s["name"] == source_name:
            return s["weight"]
    return 1.0


def recency_score(published_at):
    """Score based on how recent the article is (1.0 = just now, decays over time)"""
    if not published_at:
        return 0.5
    
    try:
        if isinstance(published_at, str):
            # Handle various ISO formats
            published_at = published_at.replace('Z', '+00:00')
            pub = datetime.fromisoformat(published_at)
        else:
            pub = published_at
        
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        hours_old = (now - pub).total_seconds() / 3600
        
        if hours_old <= 1:
            return 1.0
        elif hours_old <= RECENCY_DECAY_HOURS:
            return max(0.3, 1.0 - (hours_old / RECENCY_DECAY_HOURS) * 0.7)
        else:
            return max(0.1, 0.3 - (hours_old - RECENCY_DECAY_HOURS) / 72)
    except (ValueError, TypeError):
        return 0.5


def keyword_score(title, summary):
    """Score based on keyword matches in title and summary"""
    text = f"{title} {summary}".lower()
    total_score = 0
    matched = []
    
    for keyword, weight in INTEREST_KEYWORDS.items():
        kw_lower = keyword.lower()
        # Title match = full weight, summary match = 0.6x weight
        if kw_lower in title.lower():
            total_score += weight * 1.0
            matched.append(keyword)
        elif kw_lower in text:
            total_score += weight * 0.6
            matched.append(keyword)
    
    return total_score, matched


def heuristic_rank(articles=None):
    """Layer 1: Score all unscored articles with heuristic"""
    if articles is None:
        articles = get_unscored_articles()
    
    if not articles:
        print("No unscored articles found.")
        return 0
    
    scored = 0
    for article in articles:
        kw_score, matched = keyword_score(article["title"], article.get("summary", "") or "")
        rec_score = recency_score(article.get("published_at"))
        src_weight = get_source_weight(article["source"])
        
        # Final heuristic: keyword_score × recency × source_weight
        # Minimum score if any keyword matched
        if kw_score > 0:
            h_score = kw_score * rec_score * src_weight
        else:
            # No keyword match = low base score (still shows up, just ranked low)
            h_score = 0.1 * rec_score * src_weight
        
        update_scores(
            article["id"],
            heuristic_score=round(h_score, 4),
            final_score=round(h_score, 4),  # final = heuristic until LLM re-ranks
            keywords_matched=",".join(matched) if matched else None,
        )
        scored += 1
    
    print(f"Heuristic scored {scored} articles")
    return scored


def llm_rerank(limit=None):
    """Layer 2: Re-rank top candidates using MiMo LLM"""
    if limit is None:
        limit = TOP_CANDIDATES_FOR_RERANK
    
    articles = get_top_for_rerank(limit)
    if not articles:
        print("No articles to re-rank.")
        return 0
    
    # Build prompt with article list
    article_list = ""
    for i, a in enumerate(articles, 1):
        article_list += f"{i}. [{a['source']}] {a['title']}\n"
        if a.get('summary'):
            article_list += f"   {a['summary'][:150]}\n"
    
    prompt = f"""Kamu adalah news ranking AI. Beri skor 1-10 untuk setiap berita berdasarkan satu kriteria utama:

SEBERAPA PENTING DAN URGENT BERITA INI BAGI RAKYAT INDONESIA?

Skor tinggi (8-10): Berita yang langsung mempengaruhi hidup rakyat banyak — kebijakan ekonomi, harga pangan/BBM, lapangan kerja, anggaran negara, keputusan presiden/DPR yang berdampak luas, skandal korupsi uang rakyat.
Skor sedang (5-7): Berita politik nasional yang relevan tapi dampaknya belum langsung terasa.
Skor rendah (1-4): Berita yang tidak urgent bagi rakyat — opini, gosip politik, acara seremonial tanpa substansi, berita daerah kecil.

Berikut {len(articles)} artikel. Beri skor 1-10:

Format output HARUS JSON array:
[{{"index": 1, "score": 8}}, {{"index": 2, "score": 5}}, ...]

Artikel:
{article_list}

Output JSON saja, tanpa penjelasan:"""

    try:
        request_body = {
                "model": LLM_CONFIG["model"],
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": LLM_CONFIG["max_tokens"],
                "temperature": 0.3,
            }
        if "enable_thinking" in LLM_CONFIG:
            request_body["enable_thinking"] = LLM_CONFIG["enable_thinking"]
        
        resp = requests.post(
            f"{LLM_CONFIG['base_url']}/chat/completions",
            json=request_body,
            headers={"Authorization": f"Bearer {LLM_CONFIG['api_key']}"},
            timeout=60,
        )
        resp.raise_for_status()
        
        msg = resp.json()["choices"][0]["message"]
        content = msg.get("content") or msg.get("reasoning_content") or ""
        
        # Parse JSON from response (handle markdown code blocks)
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            scores = json.loads(json_match.group())
        else:
            print(f"Could not parse LLM response: {content[:200]}")
            return 0
        
        # Apply LLM scores
        reranked = 0
        for item in scores:
            idx = item.get("index", 0) - 1
            llm_score = item.get("score", 5)
            
            if 0 <= idx < len(articles):
                article = articles[idx]
                # Final score = heuristic (30%) + LLM (70%) — LLM judges impact & newsworthiness
                normalized_llm = llm_score / 10.0
                final = article["heuristic_score"] * 0.3 + normalized_llm * article["heuristic_score"] * 1.8
                
                update_scores(
                    article["id"],
                    llm_score=llm_score,
                    final_score=round(final, 4),
                )
                reranked += 1
        
        print(f"LLM re-ranked {reranked} articles")
        return reranked
        
    except Exception as e:
        print(f"LLM re-rank failed: {e}")
        return 0


def run_full_ranking():
    """Run both ranking layers"""
    print("=== Layer 1: Heuristic Scoring ===")
    heuristic_rank()
    
    print("\n=== Layer 2: LLM Re-ranking ===")
    llm_rerank()


if __name__ == "__main__":
    run_full_ranking()
