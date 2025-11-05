#!/usr/bin/env python3
"""
Bulk Article Upload Script

Uploads all articles from data/raw_news/ to Backend API.
Uses /api/articles/ingest endpoint with automatic deduplication.

Run this from saga-be directory:
    python scripts/upload_articles.py
    python scripts/upload_articles.py --limit 100  # Upload first 100 only
"""
import os
import sys
import json
import time
import requests
from pathlib import Path


def find_all_articles(data_dir: Path) -> list[Path]:
    """Find all article JSON files in data directory"""
    articles = []
    
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        return articles
    
    for date_dir in sorted(data_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        
        for article_file in sorted(date_dir.glob("*.json")):
            articles.append(article_file)
    
    return articles


def upload_article(article_path: Path, backend_url: str, api_key: str) -> tuple[bool, str]:
    """
    Upload single article.
    Returns (success, status_message)
    """
    try:
        with open(article_path, 'r', encoding='utf-8') as f:
            article_data = json.load(f)
        
        response = requests.post(
            f"{backend_url}/api/articles/ingest",
            json=article_data,
            headers={"X-API-Key": api_key} if api_key else {},
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        status = result.get('status', 'unknown')
        argos_id = result.get('argos_id', 'N/A')
        
        return True, f"{status} → {argos_id}"
        
    except Exception as e:
        return False, f"error: {str(e)[:50]}"


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Bulk upload articles to Backend API")
    parser.add_argument('--limit', type=int, help='Maximum number of articles to upload')
    parser.add_argument('--backend-url', type=str, 
                       default=os.getenv('BACKEND_API_URL', 'http://167.172.185.204'),
                       # default=os.getenv('BACKEND_API_URL', 'http://localhost:8000'),  # Local dev
                       help='Backend API URL')
    parser.add_argument('--api-key', type=str,
                       default=os.getenv('BACKEND_API_KEY', '785fc6c1647ff650b6b611509cc0a8f47009e6b743340503519d433f111fcf12'),
                       help='Backend API key')
    args = parser.parse_args()
    
    print("=" * 80)
    print("📤 BULK ARTICLE UPLOAD")
    print("=" * 80)
    print(f"Backend URL: {args.backend_url}")
    print(f"API Key: {'✅ Set' if args.api_key else '❌ Missing'}")
    print()
    
    # Find data directory (relative to script location)
    script_dir = Path(__file__).parent
    data_dir = (script_dir.parent / "data" / "raw_news").resolve()
    
    print(f"Data directory: {data_dir}")
    print()
    
    # Find all articles
    print("🔍 Scanning for articles...")
    articles = find_all_articles(data_dir)
    
    if not articles:
        print("❌ No articles found!")
        return 1
    
    total = len(articles)
    if args.limit:
        articles = articles[:args.limit]
        print(f"Found {total} articles, uploading first {len(articles)}")
    else:
        print(f"Found {total} articles")
    print()
    
    # Upload articles
    print("📤 Uploading articles...")
    print("-" * 80)
    
    created = 0
    existing = 0
    failed = 0
    
    start_time = time.time()
    
    for i, article_path in enumerate(articles, 1):
        success, status = upload_article(article_path, args.backend_url, args.api_key)
        
        if success:
            if 'created' in status:
                created += 1
                icon = "✅"
            else:
                existing += 1
                icon = "♻️"
        else:
            failed += 1
            icon = "❌"
        
        # Progress indicator every 10 articles or at end
        if i % 10 == 0 or i == len(articles):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            print(f"{icon} [{i}/{len(articles)}] {article_path.name} → {status} ({rate:.1f}/s)")
    
    elapsed = time.time() - start_time
    
    print("-" * 80)
    print()
    print("=" * 80)
    print("✅ UPLOAD COMPLETE!")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  ✅ Created: {created}")
    print(f"  ♻️  Existing: {existing}")
    print(f"  ❌ Failed: {failed}")
    print(f"  ⏱️  Time: {elapsed:.1f}s ({len(articles)/elapsed:.1f} articles/sec)")
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
