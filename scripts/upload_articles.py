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


def check_missing_articles(article_ids: list[str], backend_url: str, api_key: str, batch_size: int = 500) -> set[str]:
    """
    Check which articles are missing from backend.
    Returns set of article IDs that need upload.
    
    Args:
        article_ids: List of all article IDs to check
        backend_url: Backend API URL
        api_key: API key for authentication
        batch_size: Number of IDs to check per request
    
    Returns:
        Set of article IDs that are missing (need upload)
    """
    missing = set()
    total = len(article_ids)
    
    print(f"🔍 Checking existence of {total} articles in batches of {batch_size}...")
    
    # Process in batches
    for i in range(0, total, batch_size):
        batch = article_ids[i:i+batch_size]
        
        try:
            response = requests.post(
                f"{backend_url}/api/articles/check-existence",
                json=batch,
                headers={"X-API-Key": api_key} if api_key else {},
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            batch_missing = result.get('missing', [])
            missing.update(batch_missing)
            
            checked_so_far = min(i + batch_size, total)
            print(f"   Checked {checked_so_far}/{total} articles... ({len(missing)} missing so far)")
            
        except Exception as e:
            print(f"⚠️  Batch check failed for IDs {i}-{i+len(batch)}: {e}")
            # If batch check fails, assume all in batch need upload (safe fallback)
            missing.update(batch)
    
    return missing


def upload_article(article_path: Path, backend_url: str, api_key: str) -> tuple[bool, str]:
    """
    Upload single article, preserving ID from filename.
    Returns (success, status_message)
    """
    try:
        # Extract ID from filename (e.g., "0CSTSH98X.json" → "0CSTSH98X")
        article_id = article_path.stem
        
        with open(article_path, 'r', encoding='utf-8') as f:
            article_data = json.load(f)
        
        # CRITICAL: Set argos_id to preserve ID across systems
        article_data["argos_id"] = article_id
        
        response = requests.post(
            f"{backend_url}/api/articles/ingest",
            json=article_data,
            headers={"X-API-Key": api_key} if api_key else {},
            timeout=10
        )
        response.raise_for_status()
        
        result = response.json()
        status = result.get('status', 'unknown')
        reason = result.get('reason', '')
        returned_id = result.get('argos_id', 'N/A')
        
        # Verify ID was preserved
        if status == 'created' and returned_id != article_id:
            return False, f"ID mismatch: {article_id} → {returned_id}"
        
        return True, f"{status} ({reason})"
        
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
    all_articles = find_all_articles(data_dir)
    
    if not all_articles:
        print("❌ No articles found!")
        return 1
    
    print(f"✅ Found {len(all_articles)} articles")
    print()
    
    # Extract article IDs (filenames without .json)
    print("📋 Collecting article IDs...")
    article_ids = [p.stem for p in all_articles]
    print(f"✅ Collected {len(article_ids)} article IDs")
    print()
    
    # Check which articles already exist on backend
    missing_ids = check_missing_articles(article_ids, args.backend_url, args.api_key)
    
    print()
    print("📊 Existence Check Results:")
    print(f"   Total articles: {len(all_articles)}")
    print(f"   Already uploaded: {len(all_articles) - len(missing_ids)}")
    print(f"   Need to upload: {len(missing_ids)}")
    print()
    
    # Filter to only missing articles
    articles_to_upload = [p for p in all_articles if p.stem in missing_ids]
    
    # Apply limit if specified
    if args.limit and len(articles_to_upload) > args.limit:
        print(f"⚠️  Limiting upload to first {args.limit} articles")
        articles_to_upload = articles_to_upload[:args.limit]
        print()
    
    if not articles_to_upload:
        print("✅ All articles already uploaded! Nothing to do.")
        return 0
    
    # Upload missing articles
    print(f"📤 Uploading {len(articles_to_upload)} missing articles...")
    print("-" * 80)
    
    created = 0
    existing = 0
    failed = 0
    
    start_time = time.time()
    
    for i, article_path in enumerate(articles_to_upload, 1):
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
        if i % 10 == 0 or i == len(articles_to_upload):
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            print(f"{icon} [{i}/{len(articles_to_upload)}] {article_path.name} → {status} ({rate:.1f}/s)")
    
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
    print(f"  ⏱️  Time: {elapsed:.1f}s ({len(articles_to_upload)/elapsed:.1f} articles/sec)")
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
