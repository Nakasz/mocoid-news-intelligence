#!/bin/bash
# Daily: scrape → rank → export (with OG images + bullet points) → deploy mocoid
cd /home/ubuntu/news-recommender
source venv/bin/activate

echo "=== $(date) ==="
echo "1. Scraping..."
python scraper.py

echo "2. Ranking..."
python -c "from ranker import run_full_ranking; run_full_ranking()"

echo "3. Exporting articles.json with OG images + bullet points..."
python export_articles.py

echo "4. Deploying to Mocoid..."
cd /home/ubuntu/mocoid-deploy
cp /home/ubuntu/news-recommender/vercel-deploy/articles.json articles.json
cp /home/ubuntu/news-recommender/vercel-deploy/articles_inter.json articles_inter.json
# Requires VERCEL_TOKEN in environment.
npx vercel deploy --prod --yes --token "$VERCEL_TOKEN" --name mocoid 2>&1 | tail -3

echo "=== Done ==="
