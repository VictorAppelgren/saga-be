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


class ArticleStorageManager:
    """Manages file-based article storage in data/raw_news/"""
    
    def __init__(self, data_dir: str = "data/raw_news"):
        self.data_dir = Path(data_dir)
        self.today_str = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.data_dir / self.today_str
        os.makedirs(self.today_dir, exist_ok=True)
        self.article_ids = self._load_existing_ids()
        
        logger.info(f"📁 ArticleStorageManager initialized")
        logger.info(f"   Data dir: {self.data_dir.absolute()}")
        logger.info(f"   Today dir: {self.today_dir.absolute()}")
        logger.info(f"   Existing articles: {len(self.article_ids)}")
    
    def store_article(self, article_data: Dict) -> str:
        """Store article, returns argos_id"""
        argos_id = article_data.get("argos_id")
        if not argos_id:
            raise ValueError("Article must have argos_id")
        
        if argos_id in self.article_ids:
            logger.info(f"♻️  Article {argos_id} already exists, skipping")
            return argos_id
        
        file_path = self.today_dir / f"{argos_id}.json"
        logger.info(f"💾 Storing article {argos_id} to {file_path}")
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article_data, f, indent=2)
        
        self.article_ids.add(argos_id)
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
    
    def find_article_by_url(self, url: str) -> Optional[str]:
        """
        Find article by URL (deduplication check).
        Returns argos_id if found, None otherwise.
        Simple implementation: scan all articles.
        """
        if not url:
            return None
        
        for date_dir in self.data_dir.iterdir():
            if not date_dir.is_dir():
                continue
            
            for article_file in date_dir.glob("*.json"):
                try:
                    with open(article_file, 'r', encoding='utf-8') as f:
                        article = json.load(f)
                        if article.get("url") == url:
                            return article.get("argos_id")
                except Exception:
                    continue
        
        return None
    
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
                        matches.append({
                            "article_id": article_id,
                            "matched_keywords": matched_keywords,
                            "hit_count": hit_count,
                            "text_preview": text[:200] + "..." if len(text) > 200 else text
                        })
                        
                        if len(matches) >= limit:
                            return matches
                
                except Exception:
                    # Skip files that can't be read
                    continue
        
        return matches
    
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
