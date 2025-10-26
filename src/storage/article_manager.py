"""Article Storage Manager - Simple file-based storage"""
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime


class ArticleStorageManager:
    """Manages file-based article storage in data/raw_news/"""
    
    def __init__(self, data_dir: str = "data/raw_news"):
        self.data_dir = Path(data_dir)
        self.today_str = datetime.now().strftime("%Y-%m-%d")
        self.today_dir = self.data_dir / self.today_str
        os.makedirs(self.today_dir, exist_ok=True)
        self.article_ids = self._load_existing_ids()
    
    def store_article(self, article_data: Dict) -> str:
        """Store article, returns argos_id"""
        argos_id = article_data.get("argos_id")
        if not argos_id:
            raise ValueError("Article must have argos_id")
        
        if argos_id in self.article_ids:
            return argos_id
        
        file_path = self.today_dir / f"{argos_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(article_data, f, indent=2)
        
        self.article_ids.add(argos_id)
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
