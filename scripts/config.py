"""
News Recommender Pipeline - Configuration
Sources: Indonesia politik
Ranking: Heuristic + MiMo re-rank
"""

# News sources - prioritas Tempo dulu, lalu yang lain
NEWS_SOURCES = [
    # Tempo (prioritas 1)
    {"name": "Tempo Politik", "url": "https://rss.tempo.co/nasional", "type": "rss", "weight": 1.5},
    {"name": "Tempo Hukum", "url": "https://rss.tempo.co/hukum", "type": "rss", "weight": 1.4},
    
    # Detik
    {"name": "Detik News", "url": "https://news.detik.com/rss", "type": "rss", "weight": 1.2},
    
    # CNN Indonesia
    {"name": "CNN Indonesia Nasional", "url": "https://www.cnnindonesia.com/nasional/rss", "type": "rss", "weight": 1.2},
    
    # Detik Finance
    {"name": "Detik Finance", "url": "https://finance.detik.com/rss", "type": "rss", "weight": 1.1},
    
    # Kontan
    {"name": "Kontan Nasional", "url": "https://nasional.kontan.co.id/rss", "type": "rss", "weight": 1.3},
    
    # Sindo News
    {"name": "Sindo News", "url": "https://www.sindonews.com/feed", "type": "rss", "weight": 1.0},
    
    # iNews
    {"name": "iNews", "url": "https://www.inews.id/feed", "type": "rss", "weight": 1.1},
    
    # Republika
    {"name": "Republika Politik", "url": "https://www.republika.co.id/rss/nasional", "type": "rss", "weight": 1.0},

    # International (filtered to Indonesia/Prabowo articles only via INTL_KEYWORD_FILTER)
    {"name": "Bloomberg Markets", "url": "https://feeds.bloomberg.com/markets/news.rss", "type": "rss", "weight": 1.5, "intl": True},
    {"name": "Bloomberg Politics", "url": "https://feeds.bloomberg.com/politics/news.rss", "type": "rss", "weight": 1.5, "intl": True},
    {"name": "Japan Times", "url": "https://www.japantimes.co.jp/feed/", "type": "rss", "weight": 1.4, "intl": True, "use_proxy": True},
    {"name": "The Economist Asia", "url": "https://www.economist.com/asia/rss.xml", "type": "rss", "weight": 1.6, "intl": True},
    {"name": "Straits Times Asia", "url": "https://www.straitstimes.com/news/asia/rss.xml", "type": "rss", "weight": 1.4, "intl": True},
    {"name": "Nikkei Asia", "url": "https://asia.nikkei.com/rss/feed/nar", "type": "rss", "weight": 1.4, "intl": True},
]

# Keyword filter for international sources — only keep articles matching these terms
INTL_KEYWORD_FILTER = [
    "indonesia", "indonesian", "prabowo", "jakarta", "rupiah",
    "bank indonesia", "jokowi", "gibran", "ikn", "nusantara",
    "asean", "south east asia", "southeast asia",
]

# Interest keywords - bobot per keyword
# Higher weight = more relevant to user interests
INTEREST_KEYWORDS = {
    # Topik utama
    "MBG": 3.0,
    "makan bergizi gratis": 3.0,
    "makan gratis": 2.5,
    "kopdes": 3.0,
    "koperasi desa": 3.0,
    "merah putih": 2.5,
    "kopdes merahputih": 3.0,
    
    # Politik umum (high priority)
    "politik": 2.0,
    "DPR": 2.0,
    "presiden": 2.0,
    "prabowo": 2.5,
    "gibran": 2.0,
    "pemilu": 2.0,
    "pilkada": 2.0,
    
    # Politik umum (medium)
    "partai": 1.5,
    "koalisi": 1.5,
    "oposisi": 1.5,
    "menteri": 1.5,
    "kabinet": 1.5,
    "kebijakan": 1.5,
    "pemerintah": 1.5,
    "APBN": 1.8,
    "anggaran": 1.5,
    
    # Institusi
    "KPK": 1.8,
    "MK": 1.5,
    "MA": 1.3,
    "TNI": 1.3,
    "Polri": 1.3,
    
    # Isu hangat
    "korupsi": 2.0,
    "demonstrasi": 1.8,
    "demo": 1.5,
    "RUU": 1.8,
    "undang-undang": 1.5,
    "reshuffle": 2.0,
    "IKN": 1.8,
    "nusantara": 1.3,

    # Topik ekonomi & internasional (relevan utk intl sources)
    "rupiah": 2.0,
    "Bank Indonesia": 2.0,
    "ekspor": 1.8,
    "konglomerat": 1.8,
    "tycoon": 1.8,
    "crackdown": 1.8,
    "disinformasi": 1.8,
    "MBG": 3.0,
}

# Scoring parameters
RECENCY_DECAY_HOURS = 24  # artikel > 24 jam mulai turun skornya
MAX_ARTICLES_PER_SOURCE = 20
TOP_CANDIDATES_FOR_RERANK = 20  # top N artikel yang di-rerank pake LLM

# MiMo / LLM config for re-ranking
# Set MIMO_API_KEY in environment. Never commit real keys.
import os

LLM_CONFIG = {
    "base_url": os.getenv("MIMO_BASE_URL", "http://localhost:19911/v1"),
    "model": os.getenv("MIMO_MODEL", "mimo-v2.5-pro"),
    "api_key": os.getenv("MIMO_API_KEY", ""),
    "max_tokens": int(os.getenv("MIMO_MAX_TOKENS", "4000")),
    "enable_thinking": False,
}

