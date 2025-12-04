from fastapi import APIRouter
from datetime import datetime, date
from pathlib import Path
from typing import Optional
import json

router = APIRouter(prefix="/api/stats", tags=["statistics"])

# Storage directories
STATS_DIR = Path("stats/stats")
LOGS_DIR = Path("stats/logs")
STATS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/track")
async def track_stat(event_type: str, message: Optional[str] = None):
    """
    Track a single event increment.
    
    Examples:
      POST /api/stats/track?event_type=article_processed
      POST /api/stats/track?event_type=article_rejected_no_topics&message=Article ABC123: LLM found no relevant topics
    
    Stats go to JSON file for aggregation.
    Messages go to plain text log file for readability.
    """
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    log_file = LOGS_DIR / f"stats_{today}.log"
    
    # === STATS: Increment counter in JSON ===
    if stats_file.exists():
        stats = json.loads(stats_file.read_text())
    else:
        stats = {"date": today, "events": {}}
    
    stats["events"][event_type] = stats["events"].get(event_type, 0) + 1
    
    # Atomic write
    stats_file.write_text(json.dumps(stats, indent=2))
    
    # === MESSAGES: Append to plain text log ===
    if message:
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        log_line = f"{timestamp} | {event_type} | {message}\n"
        
        with open(log_file, "a") as f:
            f.write(log_line)
    
    return {"status": "ok"}


@router.get("/today")
async def get_today_stats():
    """Get today's aggregated stats (JSON only)"""
    today = date.today().isoformat()
    stats_file = STATS_DIR / f"stats_{today}.json"
    
    if not stats_file.exists():
        return {"date": today, "events": {}}
    
    return json.loads(stats_file.read_text())


@router.get("/logs/today")
async def get_today_logs():
    """Get today's message log (plain text)"""
    today = date.today().isoformat()
    log_file = LOGS_DIR / f"stats_{today}.log"
    
    if not log_file.exists():
        return {"date": today, "messages": []}
    
    # Return as plain text lines
    with open(log_file) as f:
        lines = f.readlines()
    
    return {
        "date": today,
        "log_file": str(log_file),
        "message_count": len(lines),
        "messages": [line.strip() for line in lines]
    }
