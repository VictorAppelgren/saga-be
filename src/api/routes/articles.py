"""Article API Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from pydantic import BaseModel
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
def get_article(article_id: str, x_api_key: str = Header(...)):
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
