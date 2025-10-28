"""Article API Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.storage.article_manager import ArticleStorageManager

router = APIRouter(prefix="/api/articles", tags=["articles"])
storage = ArticleStorageManager()


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
    text_preview: str


# Routes
@router.post("", response_model=ArticleResponse)
def create_article(article: ArticleCreate, x_api_key: str = Header(...)):
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
def get_article(article_id: str, x_api_key: str = Header(None)):
    """Get article by ID"""
    article = storage.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return {"argos_id": article_id, "data": article}


@router.get("")
def list_articles(
    x_api_key: str = Header(...),
    limit: int = Query(50, ge=1, le=100),
    date: Optional[str] = Query(None, regex=r"^\d{4}-\d{2}-\d{2}$")
):
    """List articles"""
    articles = storage.list_articles(limit=limit, date=date)
    return {"articles": articles, "count": len(articles)}


@router.post("/search", response_model=Dict[str, Any])
def search_articles_by_keywords(
    request: KeywordSearchRequest,
    x_api_key: str = Header(...)
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
