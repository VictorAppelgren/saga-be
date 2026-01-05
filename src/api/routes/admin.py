"""
Admin API - Statistics and Observability
Reads directly from new stats files + queries Neo4j for graph state
"""
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Dict, List
import json
import os
import requests

from src.storage.article_manager import ArticleStorageManager
from src.storage.worker_registry import get_worker_summary
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Lazy-initialized article storage (singleton)
_article_storage: ArticleStorageManager = None

def _get_article_storage() -> ArticleStorageManager:
    """Get or create article storage manager singleton."""
    global _article_storage
    if _article_storage is None:
        _article_storage = ArticleStorageManager()
    return _article_storage

# Stats directories (same as stats.py)
STATS_DIR = Path("stats/stats")
LOGS_DIR = Path("stats/logs")

# Graph API URL for Neo4j queries
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")


# ============================================================================
# DAILY STATS ENDPOINTS
# ============================================================================

@router.get("/stats/today")
def get_today_stats() -> Dict:
    """Get today's complete event statistics"""
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    
    if not stats_file.exists():
        return {"date": today, "events": {}}
    
    return json.loads(stats_file.read_text())


@router.get("/stats/{date}")
def get_stats_by_date(date_str: str) -> Dict:
    """
    Get statistics for specific date (YYYY-MM-DD)
    
    Example: /api/admin/stats/2025-12-04
    """
    try:
        # Validate date format
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    stats_file = STATS_DIR / f"stats_{date_str}.json"
    
    if not stats_file.exists():
        raise HTTPException(status_code=404, detail=f"No statistics found for {date_str}")
    
    return json.loads(stats_file.read_text())


@router.get("/stats/range")
def get_stats_range(days: int = Query(10, le=90)) -> List[Dict]:
    """
    Get statistics for the last N days (max 90)
    
    Returns list of daily stats, newest first
    """
    result = []
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            result.append(data)
        else:
            # Include empty entry for missing days
            result.append({"date": date_str, "events": {}})
    
    return result


# ============================================================================
# LOGS ENDPOINTS
# ============================================================================

@router.get("/logs/today")
def get_today_logs(lines: int = Query(100, le=10000)) -> Dict:
    """
    Get today's message log (last N lines)
    
    Returns detailed event messages with timestamps
    """
    today = date.today().isoformat()
    log_file = LOGS_DIR / f"stats_{today}.log"
    
    if not log_file.exists():
        return {
            "date": today,
            "log_file": str(log_file),
            "message_count": 0,
            "messages": []
        }
    
    with open(log_file) as f:
        all_lines = f.readlines()
    
    # Return last N lines
    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    return {
        "date": today,
        "log_file": str(log_file),
        "message_count": len(all_lines),
        "messages": [line.strip() for line in recent_lines]
    }


@router.get("/logs/{date}")
def get_logs_by_date(date_str: str, lines: int = Query(100, le=10000)) -> Dict:
    """
    Get logs for specific date (YYYY-MM-DD)
    
    Example: /api/admin/logs/2025-12-04
    """
    try:
        # Validate date format
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    log_file = LOGS_DIR / f"stats_{date_str}.log"
    
    if not log_file.exists():
        raise HTTPException(status_code=404, detail=f"No logs found for {date_str}")
    
    with open(log_file) as f:
        all_lines = f.readlines()
    
    # Return last N lines
    recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
    
    return {
        "date": date_str,
        "log_file": str(log_file),
        "message_count": len(all_lines),
        "messages": [line.strip() for line in recent_lines]
    }


# ============================================================================
# TREND ENDPOINTS (Aggregated Data for Charts)
# ============================================================================

@router.get("/trends/articles")
def get_articles_trend(days: int = Query(10, le=90)) -> Dict:
    """
    Get article ingestion trends over time
    
    Returns time series data for charting
    """
    dates = []
    fetched = []
    processed = []
    added = []
    rejected = []
    
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        dates.insert(0, date_str)  # Insert at beginning for chronological order
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})
            
            fetched.insert(0, events.get("article_fetched", 0))
            processed.insert(0, events.get("article_processed", 0))
            added.insert(0, events.get("article_added", 0))
            rejected.insert(0, events.get("article_rejected_no_topics", 0) + 
                          events.get("article_rejected_capacity", 0))
        else:
            fetched.insert(0, 0)
            processed.insert(0, 0)
            added.insert(0, 0)
            rejected.insert(0, 0)
    
    return {
        "dates": dates,
        "fetched": fetched,
        "processed": processed,
        "added": added,
        "rejected": rejected
    }


@router.get("/trends/capacity")
def get_capacity_trend(days: int = Query(10, le=90)) -> Dict:
    """
    Get capacity management trends
    
    Shows downgrades, archives, and rejections
    """
    dates = []
    downgraded = []
    archived = []
    rejected = []
    
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        dates.insert(0, date_str)
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})
            
            downgraded.insert(0, events.get("article_downgraded", 0))
            archived.insert(0, events.get("article_archived", 0))
            rejected.insert(0, events.get("article_rejected_capacity", 0))
        else:
            downgraded.insert(0, 0)
            archived.insert(0, 0)
            rejected.insert(0, 0)
    
    return {
        "dates": dates,
        "downgraded": downgraded,
        "archived": archived,
        "rejected": rejected
    }


@router.get("/trends/topics")
def get_topics_trend(days: int = Query(10, le=90)) -> Dict:
    """
    Get topic management trends
    
    Shows topic creation and rejection
    """
    dates = []
    created = []
    rejected = []
    deleted = []
    
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        dates.insert(0, date_str)
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})
            
            created.insert(0, events.get("topic_created", 0))
            rejected.insert(0, events.get("topic_rejected", 0))
            deleted.insert(0, events.get("topic_deleted", 0))
        else:
            created.insert(0, 0)
            rejected.insert(0, 0)
            deleted.insert(0, 0)
    
    return {
        "dates": dates,
        "created": created,
        "rejected": rejected,
        "deleted": deleted
    }


@router.get("/trends/queries")
def get_queries_trend(days: int = Query(10, le=90)) -> Dict:
    """
    Get query execution trends
    
    Shows API query activity over time
    """
    dates = []
    queries = []
    
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        dates.insert(0, date_str)
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})
            
            queries.insert(0, events.get("query_executed", 0))
        else:
            queries.insert(0, 0)
    
    return {
        "dates": dates,
        "queries": queries
    }


@router.get("/trends/analysis")
def get_analysis_trend(days: int = Query(10, le=90)) -> Dict:
    """
    Get agent analysis trends

    Shows analysis triggers, completions, skips, and sections written
    """
    dates = []
    triggered = []
    completed = []
    skipped_no_new = []
    skipped_cooldown = []
    sections = []

    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"

        dates.insert(0, date_str)

        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})

            triggered.insert(0, events.get("analysis.triggered.new_articles", 0))
            completed.insert(0, events.get("agent_analysis_completed", 0))
            skipped_no_new.insert(0, events.get("analysis.skipped.no_new_articles", 0))
            skipped_cooldown.insert(0, events.get("analysis.skipped.cooldown", 0))
            sections.insert(0, events.get("agent_section_written", 0))
        else:
            triggered.insert(0, 0)
            completed.insert(0, 0)
            skipped_no_new.insert(0, 0)
            skipped_cooldown.insert(0, 0)
            sections.insert(0, 0)

    return {
        "dates": dates,
        "triggered": triggered,
        "completed": completed,
        "skipped_no_new": skipped_no_new,
        "skipped_cooldown": skipped_cooldown,
        "sections": sections
    }


@router.get("/trends/strategy-analysis")
def get_strategy_analysis_trend(days: int = Query(10, le=90)) -> Dict:
    """Get strategy analysis trends (custom user strategies)"""
    dates = []
    triggered = []
    completed = []
    
    today = date.today()
    
    for i in range(days):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()
        stats_file = STATS_DIR / f"stats_{date_str}.json"
        
        dates.insert(0, date_str)
        
        if stats_file.exists():
            data = json.loads(stats_file.read_text())
            events = data.get("events", {})
            triggered.insert(0, events.get("strategy_analysis_triggered", 0))
            completed.insert(0, events.get("strategy_analysis_completed", 0))
        else:
            triggered.insert(0, 0)
            completed.insert(0, 0)
    
    return {
        "dates": dates,
        "triggered": triggered,
        "completed": completed
    }


# ============================================================================
# SUMMARY ENDPOINT (Dashboard Overview)
# ============================================================================

@router.get("/summary")
def get_admin_summary() -> Dict:
    """
    Get high-level summary for admin dashboard
    
    Returns today's key metrics + graph state from Neo4j
    """
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    
    # Get event stats
    if stats_file.exists():
        data = json.loads(stats_file.read_text())
        events = data.get("events", {})
    else:
        events = {}
    
    # Get graph state from Neo4j
    graph_state = _get_graph_state()

    # Get cold storage stats
    cold_storage = _get_article_storage().get_stats()

    return {
        "date": today,
        "cold_storage": cold_storage,
        "pipeline": {
            "queries": events.get("query_executed", 0),
            "fetched": events.get("article_fetched", 0),
            "processed": events.get("article_processed", 0),
            "added": events.get("article_added", 0),
            "rejected": events.get("article_rejected_no_topics", 0) + 
                       events.get("article_rejected_capacity", 0)
        },
        "tier_breakdown": {
            "tier_3": events.get("article_classified_priority_3", 0),
            "tier_2": events.get("article_classified_priority_2", 0),
            "tier_1": events.get("article_classified_priority_1", 0),
            "tier_0": events.get("article_classified_priority_0", 0),
        },
        "capacity": {
            "downgraded": events.get("article_downgraded", 0),
            "archived": events.get("article_archived", 0),
            "rejected_capacity": events.get("article_rejected_capacity", 0),
            "duplicates_skipped": events.get("article_duplicate_skipped", 0)
        },
        "topics": {
            "suggested": events.get("topic_suggested", 0),
            "created": events.get("topic_created", 0),
            "rejected": events.get("topic_rejected", 0),
            "rejected_no_proposal": events.get("topic_rejected_no_proposal", 0),
            "rejected_relevance": events.get("topic_rejected_relevance", 0),
            "rejected_capacity": events.get("topic_rejected_capacity", 0),
            "deleted": events.get("topic_deleted", 0)
        },
        "analysis": {
            "triggered": events.get("analysis.triggered.new_articles", 0),
            "completed": events.get("agent_analysis_completed", 0),
            "skipped_no_new": events.get("analysis.skipped.no_new_articles", 0),
            "skipped_cooldown": events.get("analysis.skipped.cooldown", 0),
            "sections": events.get("agent_section_written", 0)
        },
        "strategy_analysis": {
            "triggered": events.get("strategy_analysis_triggered", 0),
            "completed": events.get("strategy_analysis_completed", 0)
        },
        "exploration": {
            "started": events.get("exploration_started", 0),
            "accepted": events.get("exploration_accepted", 0),
            "rejected": events.get("exploration_rejected", 0)
        },
        "llm_calls": {
            "simple": events.get("llm_call_simple", 0),
            "medium": events.get("llm_call_medium", 0),
            "complex": events.get("llm_call_complex", 0),
            "fast": events.get("llm_call_fast", 0)
        },
        "engagement": {
            "sessions": events.get("user_session_started", 0),
            "strategies_created": events.get("strategy_created", 0),
            "strategies_viewed": events.get("strategy_viewed", 0),
            "reports_viewed": events.get("report_viewed", 0),
            "section_rewrites": events.get("analysis_section_rewrite", 0)
        },
        "graph_state": graph_state,
        "errors": events.get("error_occurred", 0)
    }


def _get_graph_state() -> Dict:
    """
    Query Neo4j for current graph state via Graph API

    Returns counts and averages for capacity monitoring
    """
    url = f"{GRAPH_API_URL}/neo/graph-state"
    logger.info(f"[GRAPH_STATE] Fetching from: {url}")

    try:
        response = requests.get(url, timeout=5)
        logger.info(f"[GRAPH_STATE] Response status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"[GRAPH_STATE] Non-200 response: {response.status_code} - {response.text[:200]}")
            return _empty_graph_state()

        data = response.json()
        logger.info(f"[GRAPH_STATE] Success: topics={data.get('topics')}, articles={data.get('articles')}")
        return data

    except requests.exceptions.ConnectionError as e:
        logger.error(f"[GRAPH_STATE] Connection error to {url}: {e}")
        return _empty_graph_state()
    except requests.exceptions.Timeout as e:
        logger.error(f"[GRAPH_STATE] Timeout connecting to {url}: {e}")
        return _empty_graph_state()
    except Exception as e:
        logger.error(f"[GRAPH_STATE] Unexpected error: {type(e).__name__}: {e}")
        return _empty_graph_state()


def _empty_graph_state() -> Dict:
    """Return empty graph state on error"""
    return {
        "topics": 0,
        "articles": 0,
        "connections": 0,
        "avg_articles_per_topic": 0
    }


# ============================================================================
# TOPICS ENDPOINTS (Proxy to Graph API)
# ============================================================================

@router.get("/topics")
def get_all_topics():
    """
    Get all topics from Neo4j
    
    Proxies to Graph API for Neo4j queries
    """
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/topics/all", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/topics/{topic_id}")
def get_topic_details(topic_id: str):
    """
    Get detailed topic information including article stats

    Proxies to Graph API for Neo4j queries
    """
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/reports/{topic_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.get("/topics-recent")
def get_recent_topics(days: int = Query(default=7, le=30)):
    """
    Get recently created topics grouped by day.

    Returns: {today: [...], yesterday: [...], this_week: [...]}
    """
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/topics/recent?days={days}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str):
    """
    Delete a topic from Neo4j.

    Removes the topic and all its relationships.
    """
    try:
        response = requests.delete(f"{GRAPH_API_URL}/neo/topics/{topic_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# GRAPH STATE ENDPOINT
# ============================================================================

@router.get("/graph/state")
def get_graph_state_detailed() -> Dict:
    """
    Get detailed graph state from Neo4j
    
    Returns comprehensive graph metrics for monitoring
    """
    return _get_graph_state()


# ============================================================================
# COLD STORAGE ENDPOINTS
# ============================================================================

@router.get("/cold-storage/stats")
def get_cold_storage_stats() -> Dict:
    """
    Get cold storage (file-based) article statistics.

    Returns total articles, date range, and URL cache size.
    """
    storage = _get_article_storage()
    return storage.get_stats()


@router.get("/article-distribution")
def get_article_distribution() -> Dict:
    """
    Get article distribution by timeframe and perspective from Neo4j.

    Returns counts per topic for each timeframe × perspective combination.
    """
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/article-distribution", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============================================================================
# WORKERS ENDPOINT
# ============================================================================

@router.get("/workers")
def get_workers() -> Dict:
    """
    Get all workers with active status.

    Workers are considered active if seen in the last 5 minutes.
    Returns worker list and summary counts.
    """
    return get_worker_summary()


# ============================================================================
# DEBUG ENDPOINTS
# ============================================================================

@router.get("/stats/debug/files")
def debug_stats_files():
    """
    Debug: List all available stats files
    """
    if not STATS_DIR.exists():
        return {"error": "Stats directory does not exist", "files": []}
    
    files = sorted([f.name for f in STATS_DIR.glob("*.json")])
    
    return {
        "stats_dir": str(STATS_DIR.absolute()),
        "file_count": len(files),
        "files": files
    }


@router.get("/stats/debug/latest")
def debug_latest_stats():
    """
    Debug: Show raw contents of the latest stats file
    """
    if not STATS_DIR.exists():
        return {"error": "Stats directory does not exist"}
    
    files = sorted(STATS_DIR.glob("*.json"), reverse=True)
    
    if not files:
        return {"error": "No stats files found"}
    
    latest = files[0]
    
    return {
        "file": latest.name,
        "path": str(latest.absolute()),
        "contents": json.loads(latest.read_text())
    }
