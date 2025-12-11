"""Article Storage Manager - Simple file-based storage"""
import os
import json
import re
import random
import string
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


def unwrap_article(article: Dict) -> Dict:
    """Unwrap nested data wrappers from corrupted articles. Single source of truth."""
    original_size = len(str(article))
    result = article
    while isinstance(result.get("data"), dict) and ("url" in result["data"] or "argos_id" in result["data"]):
        result = result["data"]
    
    # Safety check: unwrapped should be at least 80% of original (prevent saving empty)
    result_size = len(str(result))
    if result_size < original_size * 0.8:
        logger.warning(f"Unwrap safety check failed: {result_size} < 80% of {original_size}, keeping original")
        return article
    return result


class ArticleStorageManager:
    """Manages file-based article storage in data/raw_news/"""
    
    def __init__(self, data_dir: str = "data/raw_news"):
        self.data_dir = Path(data_dir)
        self.today_str = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.data_dir / self.today_str
        os.makedirs(self.today_dir, exist_ok=True)
        self.article_ids = self._load_existing_ids()
        
        # URL cache for fast deduplication (critical for performance)
        # WHY: Without cache, URL lookups require scanning ALL article files (slow O(n))
        # WITH cache: URL lookups are instant hash table lookups (fast O(1))
        # Example: 18k articles → without cache = 30+ min, with cache = 2 min
        # Built once on startup, updated on each new article store
        self.url_to_id: Dict[str, str] = {}
        self._build_url_cache()
        
        logger.info(f"📁 ArticleStorageManager initialized")
        logger.info(f"   Data dir: {self.data_dir.absolute()}")
        logger.info(f"   Today dir: {self.today_dir.absolute()}")
        logger.info(f"   Existing articles: {len(self.article_ids)}")
        logger.info(f"   URL cache: {len(self.url_to_id)} URLs indexed")
    
    def store_article(self, article_data: Dict) -> str:
        """Store article, returns argos_id. Auto-unwraps nested data."""
        # Always unwrap before storing to prevent/fix corruption
        article_data = unwrap_article(article_data)
        
        argos_id = article_data.get("argos_id")
        if not argos_id:
            raise ValueError("Article must have argos_id")
        
        if argos_id in self.article_ids:
            logger.info(f"♻️  Article {argos_id} already exists, skipping")
            return argos_id
        
        # Use article's publication date for directory, fallback to today
        pub_date = article_data.get("pubDate") or article_data.get("published_date")
        if pub_date:
            # Extract YYYY-MM-DD from various formats
            # Handles: "2025-10-31", "2025-10-31T12:00:00", "2025-10-31T12:00:00+05:30"
            date_str = pub_date.split("T")[0]
            target_dir = self.data_dir / date_str
            os.makedirs(target_dir, exist_ok=True)
        else:
            # Fallback to today if no publication date
            target_dir = self.today_dir
            logger.warning(f"No publication date for {argos_id}, using today's directory")
        
        file_path = target_dir / f"{argos_id}.json"
        logger.info(f"💾 Storing article {argos_id} to {file_path}")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article_data, f, indent=2)
        
        # Update caches (keep in sync with filesystem)
        self.article_ids.add(argos_id)
        url = article_data.get("url")
        if url:
            # Add to URL cache so future lookups are instant
            self.url_to_id[url] = argos_id
        
        logger.info(f"✅ Article {argos_id} stored successfully")
        return argos_id
    
    def get_article(self, article_id: str) -> Optional[Dict]:
        """Load article by ID from any date directory"""
        for date_dir in self.data_dir.iterdir():
            if not date_dir.is_dir():
                continue
            file_path = date_dir / f"{article_id}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        return None
    
    def list_articles(self, limit: int = 50, date: Optional[str] = None) -> List[Dict]:
        """List recent articles"""
        if date:
            search_dirs = [self.data_dir / date] if (self.data_dir / date).exists() else []
        else:
            search_dirs = sorted([d for d in self.data_dir.iterdir() if d.is_dir()], reverse=True)
        
        articles = []
        for date_dir in search_dirs:
            json_files = sorted(date_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for file_path in json_files:
                if len(articles) >= limit:
                    break
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        articles.append(json.load(f))
                except Exception:
                    continue
            if len(articles) >= limit:
                break
        
        return articles[:limit]
    
    def _load_existing_ids(self) -> Set[str]:
        """Load all existing article IDs"""
        ids = set()
        for root, _, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith(".json"):
                    ids.add(file.replace(".json", ""))
        return ids
    
    def _build_url_cache(self):
        """
        Build URL→ID cache on startup for fast lookups.
        
        This is a one-time scan of all article files to build an in-memory
        index of URL→article_id mappings. After this, URL deduplication
        checks become instant instead of requiring file scans.
        
        Performance: ~2 seconds for 18k articles on startup.
        Benefit: Saves 30+ minutes during bulk uploads.
        """
        count = 0
        for date_dir in self.data_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            for article_file in date_dir.glob("*.json"):
                try:
                    with open(article_file, 'r', encoding='utf-8') as f:
                        article = json.load(f)
                        url = article.get("url")
                        if url:
                            article_id = article_file.stem
                            self.url_to_id[url] = article_id
                            count += 1
                except Exception:
                    continue
    
    def find_article_by_url(self, url: str) -> Optional[str]:
        """
        Find article by URL using cache (fast).
        
        Uses in-memory URL→ID cache for O(1) lookup instead of O(n) file scan.
        This is critical for deduplication during bulk uploads and live ingestion.
        
        Returns:
            article_id if URL exists, None otherwise
        """
        if not url:
            return None
        
        # Check cache (instant hash table lookup - O(1))
        return self.url_to_id.get(url)
    
    def _build_keyword_pattern(self, kw: str) -> re.Pattern:
        """Build regex pattern for keyword matching with flexible separators"""
        s = kw.lower().strip()
        parts = re.split(r"[-/\s]+", s)
        parts = [p for p in parts if p]
        if not parts:
            inner = re.escape(s)
        else:
            inner = r"(?:[-/\s]?)".join(re.escape(p) for p in parts)
        pattern = rf"(?<![a-z0-9]){inner}(?![a-z0-9])"
        return re.compile(pattern)
    
    def search_by_keywords(
        self,
        keywords: List[str],
        limit: int = 5,
        min_hits: int = 3,
        exclude_ids: Optional[Set[str]] = None
    ) -> List[Dict]:
        """
        Search articles by keyword matching.
        Returns list of article IDs with metadata sorted by relevance.
        
        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results
            min_hits: Minimum number of keyword matches required
            exclude_ids: Set of article IDs to skip
        
        Returns:
            [
                {
                    "article_id": "ABC123",
                    "matched_keywords": ["fed", "rate"],
                    "hit_count": 2,
                    "text_preview": "..."
                },
                ...
            ]
        """
        exclude_ids = exclude_ids or set()
        
        # Prepare keywords and patterns
        kw_lower = []
        seen = set()
        for k in keywords:
            if not k:
                continue
            kk = k.lower()
            if kk in seen:
                continue
            seen.add(kk)
            kw_lower.append(kk)
        
        compiled = [(k, self._build_keyword_pattern(k)) for k in kw_lower]
        matches = []
        scanned = 0
        
        # Get all date directories, sorted newest first
        days = [d for d in self.data_dir.iterdir() if d.is_dir()]
        days_sorted = sorted(days, key=lambda p: p.name, reverse=True)
        
        for day_dir in days_sorted:
            json_files = sorted(day_dir.glob("*.json"), key=lambda p: p.name, reverse=True)
            
            for file_path in json_files:
                scanned += 1
                article_id = file_path.stem
                
                # Skip excluded articles
                if article_id in exclude_ids:
                    continue
                
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        article_data = json.load(f)
                    
                    # Extract text fields (handle both wrapped and unwrapped formats)
                    data = article_data.get("data", article_data)
                    title = data.get("title", "")
                    summary = data.get("summary", "") or data.get("description", "")
                    argos_summary = data.get("argos_summary", "")
                    
                    # Concatenate text
                    text = " ".join([title, summary, argos_summary]).strip()
                    text_lower = text.lower()
                    
                    # Match keywords
                    matched_keywords = [k for (k, pat) in compiled if pat.search(text_lower)]
                    hit_count = len(matched_keywords)
                    
                    # Check if meets threshold
                    if hit_count >= min_hits:
                        # Return full article object (like old logic)
                        matches.append({
                            "article_id": article_id,
                            "matched_keywords": matched_keywords,
                            "hit_count": hit_count,
                            "article": article_data  # Full article object
                        })
                        
                        if len(matches) >= limit:
                            return matches
                
                except Exception:
                    # Skip files that can't be read
                    continue
        
        return matches
    
    def article_exists(self, article_id: str) -> bool:
        """
        Check if article exists in storage (fast file check).
        
        Searches all date directories for the article file.
        Uses in-memory cache first, then scans filesystem.
        
        Args:
            article_id: Article ID to check
        
        Returns:
            True if article exists, False otherwise
        """
        # Quick check in memory cache
        if article_id in self.article_ids:
            return True
        
        # Scan all date directories (newest first)
        date_dirs = sorted(
            [d for d in self.data_dir.iterdir() if d.is_dir()],
            reverse=True
        )
        
        for date_dir in date_dirs:
            file_path = date_dir / f"{article_id}.json"
            if file_path.exists():
                # Update cache
                self.article_ids.add(article_id)
                return True
        
        return False
    
    def generate_article_id(self) -> str:
        """
        Generate a unique 9-character article ID.
        Format: Uppercase letters + digits (e.g., ABC123XYZ)
        Checks against existing IDs to ensure uniqueness.
        """
        charset = string.ascii_uppercase + string.digits
        
        while True:
            # Generate random 9-char ID
            new_id = ''.join(random.choices(charset, k=9))
            
            # Ensure it's unique
            if new_id not in self.article_ids:
                return new_id
    
    def find_by_url_date(self, url: str, published_date: str) -> Optional[str]:
        """
        Find article by URL and published date (deduplication check).
        
        Scans recent date directories (last 30 days) for matching article.
        Returns article ID if found, None if not found.
        
        Args:
            url: Article URL
            published_date: Publication date (YYYY-MM-DD format)
        
        Returns:
            Article ID if duplicate found, None otherwise
        """
        if not url or not published_date:
            return None
        
        # Get date directories to search (sorted newest first)
        date_dirs = sorted(
            [d for d in self.data_dir.iterdir() if d.is_dir()],
            reverse=True
        )
        
        # Limit search to last 30 directories (roughly 30 days)
        date_dirs = date_dirs[:30]
        
        # Scan each directory for matching article
        for date_dir in date_dirs:
            for file_path in date_dir.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        article = json.load(f)
                    
                    # Check if URL and date match
                    article_data = article.get("data", article)
                    if (article_data.get("url") == url and 
                        article_data.get("published_date") == published_date):
                        # Found duplicate! Return existing ID
                        return file_path.stem  # filename without .json
                
                except Exception:
                    # Skip files that can't be read
                    continue
        
        # No duplicate found
        return None
    
    def cleanup_corrupted_files(self, dry_run: bool = True) -> dict:
        """
        Fix corrupted article files with nested data wrappers directly on disk.
        Run this on the server to avoid network overhead.
        
        Args:
            dry_run: If True, only report what would be fixed without modifying files
        
        Returns:
            Stats dict with total, corrupted, fixed counts
        """
        stats = {"total": 0, "corrupted": 0, "fixed": 0, "errors": 0}
        
        for date_dir in self.data_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            for file_path in date_dir.glob("*.json"):
                stats["total"] += 1
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        article = json.load(f)
                    
                    # Check if nested
                    unwrapped = unwrap_article(article)
                    if unwrapped is not article:  # Was unwrapped
                        stats["corrupted"] += 1
                        if not dry_run:
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(unwrapped, f, indent=2)
                            stats["fixed"] += 1
                
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Error processing {file_path}: {e}")
                
                # Progress every 5000
                if stats["total"] % 5000 == 0:
                    logger.info(f"Progress: {stats['total']} scanned, {stats['corrupted']} corrupted")
        
        return stats


# CLI for direct server-side cleanup
if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    parser = argparse.ArgumentParser(description="Article storage cleanup")
    parser.add_argument("--fix", action="store_true", help="Actually fix files (default is dry-run)")
    parser.add_argument("--data-dir", default="data/raw_news", help="Data directory path")
    args = parser.parse_args()
    
    storage = ArticleStorageManager(data_dir=args.data_dir)
    
    mode = "FIXING" if args.fix else "DRY-RUN"
    logger.info(f"🧹 Starting cleanup ({mode})...")
    
    stats = storage.cleanup_corrupted_files(dry_run=not args.fix)
    
    logger.info(f"✅ Done!")
    logger.info(f"   Total:     {stats['total']}")
    logger.info(f"   Corrupted: {stats['corrupted']}")
    logger.info(f"   Fixed:     {stats['fixed']}")
    logger.info(f"   Errors:    {stats['errors']}")
