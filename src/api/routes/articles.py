"""Article API Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import logging

from src.storage.article_manager import ArticleStorageManager

router = APIRouter(prefix="/api/articles", tags=["articles"])
storage = ArticleStorageManager()
logger = logging.getLogger(__name__)


# Models
class ArticleCreate(BaseModel):
    argos_id: str
    data: Dict[str, Any]
    query_id: Optional[str] = None
    timestamp: Optional[str] = None


class ArticleResponse(BaseModel):
    argos_id: str
    data: Dict[str, Any]


class KeywordSearchRequest(BaseModel):
    keywords: List[str] = Field(..., description="List of keywords to search for")
    limit: int = Field(5, ge=1, le=50, description="Maximum number of results")
    min_keyword_hits: int = Field(3, ge=1, description="Minimum keyword matches required")
    exclude_ids: Optional[List[str]] = Field(None, description="Article IDs to exclude")


class KeywordSearchResult(BaseModel):
    article_id: str
    matched_keywords: List[str]
    hit_count: int
    full_text: str


# Routes
@router.post("", response_model=ArticleResponse)
def create_article(article: ArticleCreate):
    """Store a new article"""
    try:
        article_data = article.dict()
        argos_id = storage.store_article(article_data)
        return {"argos_id": argos_id, "data": article_data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: str):
    """Get article by ID"""
    article = storage.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"argos_id": article_id, "data": article}


@router.get("")
def list_articles(
    limit: int = Query(50, ge=1, le=100),
    date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$")
):
    """List articles"""
    articles = storage.list_articles(limit=limit, date=date)
    return {"articles": articles, "count": len(articles)}


@router.post("/search", response_model=Dict[str, Any])
def search_articles_by_keywords(
    request: KeywordSearchRequest
):
    """
    Search articles by keyword matching.
    
    Scans article storage and returns articles that match at least min_keyword_hits keywords.
    Uses fuzzy matching to handle variations in separators (spaces, hyphens, slashes).
    
    Example:
        POST /api/articles/search
        {
            "keywords": ["fed", "rate", "inflation"],
            "limit": 5,
            "min_keyword_hits": 2,
            "exclude_ids": ["ABC123"]
        }
    """
    try:
        results = storage.search_by_keywords(
            keywords=request.keywords,
            limit=request.limit,
            min_hits=request.min_keyword_hits,
            exclude_ids=set(request.exclude_ids) if request.exclude_ids else None
        )
        return {
            "results": results,
            "count": len(results),
            "searched_keywords": request.keywords,
            "min_hits": request.min_keyword_hits
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.post("/ingest")
def ingest_article(article_data: Dict[str, Any]):
    """
    Ingest article with automatic deduplication.
    
    Checks if article already exists (by URL + date).
    - If exists: Returns existing article ID
    - If new: Generates ID, stores article, returns new ID
    
    This is the PRIMARY endpoint for workers to use.
    Backend controls ID generation to prevent duplicates.
    
    Example:
        POST /api/articles/ingest
        {
            "url": "https://...",
            "title": "Fed raises rates",
            "published_date": "2025-10-31",
            "content": "...",
            ...
        }
    
    Returns:
        {
            "argos_id": "ABC123XYZ",
            "status": "created" | "existing",
            "data": {...}
        }
    """
    try:
        # Extract URL for deduplication check
        url = article_data.get("url")
        
        logger.info(f"📥 Ingest request: {url}")
        
        if not url:
            raise HTTPException(
                status_code=400,
                detail="Article must have 'url'"
            )
        
        # Check if article already exists by URL
        existing_id = storage.find_article_by_url(url)
        
        if existing_id:
            # Duplicate found - return existing article
            logger.info(f"♻️  Duplicate article detected: {url} → {existing_id}")
            existing_article = storage.get_article(existing_id)
            return {
                "argos_id": existing_id,
                "status": "existing",
                "data": existing_article
            }
        
        # New article - generate ID and store
        argos_id = storage.generate_article_id()
        article_data["argos_id"] = argos_id
        
        logger.info(f"🆕 New article ID: {argos_id}")
        logger.info(f"💾 Calling storage.store_article()...")
        
        # Store article
        storage.store_article(article_data)
        
        logger.info(f"✅ Article {argos_id} ingested successfully")
        return {
            "argos_id": argos_id,
            "status": "created",
            "data": article_data
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(status_code=500, detail=f"Ingest error: {str(e)}")


@router.post("/bulk")
def bulk_import_articles(
    articles: List[Dict[str, Any]],
    overwrite: bool = False
):
    """
    Bulk import articles (for restore operations).
    
    Accepts articles WITH existing argos_id values.
    Used for restoring server from laptop backup.
    
    Args:
        articles: List of article objects (must include argos_id)
        overwrite: If True, overwrites existing articles. If False, skips duplicates.
    
    Example:
        POST /api/articles/bulk
        {
            "articles": [
                {"argos_id": "ABC123", "url": "...", ...},
                {"argos_id": "XYZ789", "url": "...", ...}
            ],
            "overwrite": false
        }
    
    Returns:
        {
            "imported": 150,
            "skipped": 5,
            "errors": 0
        }
    """
    imported = 0
    skipped = 0
    errors = 0
    
    for article in articles:
        try:
            # Check if article has ID
            argos_id = article.get("argos_id")
            if not argos_id:
                logger.warning("Bulk import: Article missing argos_id, skipping")
                errors += 1
                continue
            
            # Check if article already exists
            if argos_id in storage.article_ids:
                if not overwrite:
                    # Skip existing article
                    skipped += 1
                    continue
            
            # Store article with existing ID
            storage.store_article(article)
            imported += 1
        
        except Exception as e:
            logger.error(f"Bulk import error for article: {e}")
            errors += 1
    
    logger.info(f"Bulk import complete: {imported} imported, {skipped} skipped, {errors} errors")
    
    return {
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "total": len(articles)
    }
