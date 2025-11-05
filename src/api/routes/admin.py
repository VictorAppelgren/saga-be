"""
Admin Routes - Proxy to Graph API Admin Endpoints
Forwards requests from frontend to Graph API (port 8001)
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List
import requests
import os

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Graph API URL (internal Docker network)
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://saga-apis:8001")


# ============================================================================
# DAILY STATS ENDPOINTS
# ============================================================================

@router.get("/stats/today")
def get_today_stats():
    """Get today's complete statistics"""
    try:
        response = requests.get(f"{GRAPH_API_URL}/api/admin/stats/today", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/stats/{date}")
def get_stats_by_date(date: str):
    """Get statistics for specific date (YYYY-MM-DD)"""
    try:
        response = requests.get(f"{GRAPH_API_URL}/api/admin/stats/{date}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No statistics found for {date}")
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/stats/range")
def get_stats_range(days: int = Query(10, le=90)):
    """Get statistics for the last N days"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/stats/range",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# TREND DATA ENDPOINTS
# ============================================================================

@router.get("/trends/articles")
def get_articles_trend(days: int = Query(10, le=90)):
    """Get article ingestion trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/articles",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/trends/analysis")
def get_analysis_trend(days: int = Query(10, le=90)):
    """Get analysis generation trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/analysis",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/trends/graph")
def get_graph_trend(days: int = Query(10, le=90)):
    """Get graph growth trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/graph",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/trends/llm")
def get_llm_trend(days: int = Query(10, le=90)):
    """Get LLM usage trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/llm",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/trends/queries")
def get_queries_trend(days: int = Query(10, le=90)):
    """Get query processing trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/queries",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/trends/errors")
def get_errors_trend(days: int = Query(10, le=90)):
    """Get error trends"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/trends/errors",
            params={"days": days},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# LOGS ENDPOINTS
# ============================================================================

@router.get("/logs/today")
def get_today_logs(lines: int = Query(100, le=1000)):
    """Get today's master log"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/logs/today",
            params={"lines": lines},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/logs/{date}")
def get_logs_by_date(date: str, lines: int = Query(100, le=1000)):
    """Get logs for specific date"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/api/admin/logs/{date}",
            params={"lines": lines},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"No logs found for {date}")
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# SUMMARY ENDPOINT
# ============================================================================

@router.get("/summary")
def get_admin_summary():
    """Get high-level summary for admin dashboard"""
    try:
        response = requests.get(f"{GRAPH_API_URL}/api/admin/summary", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# TOPICS ENDPOINTS
# ============================================================================

@router.get("/topics")
def get_all_topics():
    """Get all topics from Neo4j"""
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/topics/all", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/topics/{topic_id}")
def get_topic_details(topic_id: str):
    """Get detailed topic information including articles and reports"""
    try:
        response = requests.post(
            f"{GRAPH_API_URL}/neo/build-context",
            params={"topic_id": topic_id},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
