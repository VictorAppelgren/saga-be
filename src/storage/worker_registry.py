"""
Worker Registry - SQLite-based worker tracking

Workers send X-Worker-ID and X-Worker-Task headers on API calls.
This module stores and retrieves worker status.

Active = last seen within 5 minutes.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# SQLite file location
DB_PATH = Path("/tmp/saga_workers.db")


def _get_conn() -> sqlite3.Connection:
    """Get SQLite connection, create table if needed."""
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            worker_id TEXT PRIMARY KEY,
            machine TEXT,
            current_task TEXT,
            last_seen TEXT
        )
    """)
    conn.commit()
    return conn


def update_worker(worker_id: str, machine: str, task: Optional[str] = None) -> None:
    """Update worker status (called by middleware on each request)."""
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO workers (worker_id, machine, current_task, last_seen)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(worker_id) DO UPDATE SET
                machine = excluded.machine,
                current_task = excluded.current_task,
                last_seen = excluded.last_seen
            """,
            (worker_id, machine, task, datetime.utcnow().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_all_workers(active_minutes: int = 5) -> List[Dict]:
    """Get all workers with active status."""
    conn = _get_conn()
    try:
        cursor = conn.execute("SELECT worker_id, machine, current_task, last_seen FROM workers")
        rows = cursor.fetchall()
    finally:
        conn.close()

    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=active_minutes)

    workers = []
    for row in rows:
        worker_id, machine, task, last_seen_str = row
        try:
            last_seen = datetime.fromisoformat(last_seen_str)
            is_active = last_seen > cutoff
            seconds_ago = int((now - last_seen).total_seconds())
        except:
            is_active = False
            seconds_ago = 9999

        workers.append({
            "worker_id": worker_id,
            "machine": machine,
            "current_task": task or "idle",
            "last_seen": last_seen_str,
            "active": is_active,
            "seconds_ago": seconds_ago
        })

    return workers


def get_worker_summary(active_minutes: int = 5) -> Dict:
    """Get summary stats for workers."""
    workers = get_all_workers(active_minutes)
    active_count = sum(1 for w in workers if w["active"])

    return {
        "total_workers": len(workers),
        "active": active_count,
        "inactive": len(workers) - active_count,
        "workers": workers
    }
