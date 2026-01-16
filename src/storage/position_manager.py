"""
Position Storage Manager - Tracks actual positions entered/exited by users.

A Position is a snapshot of a strategy at the moment of entry, plus tracking fields.
Positions are stored in: users/{username}/positions/pos_{timestamp}_{asset}.json
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class PositionStorageManager:
    """Manages file-based position storage in users/{username}/positions/"""

    def __init__(self, users_dir: str = "users"):
        self.users_dir = Path(users_dir)

    def _get_positions_dir(self, username: str) -> Path:
        """Get positions directory for user."""
        return self.users_dir / username / "positions"

    def create_position(
        self,
        username: str,
        strategy_id: str,
        strategy_snapshot: Dict,
        entry_price: float,
        direction: str,
        target_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        notes: str = "",
        ai_suggested: bool = True,
        ai_confidence: str = "medium",
    ) -> Dict:
        """
        Create a new position from strategy snapshot.

        Args:
            username: User who owns the position
            strategy_id: ID of the strategy this position is for
            strategy_snapshot: Full strategy state at time of entry
            entry_price: Price at which position was entered
            direction: "long" or "short"
            target_price: Optional target price
            stop_loss: Optional stop loss price
            notes: Optional notes
            ai_suggested: Whether AI suggested this entry
            ai_confidence: AI confidence level if suggested

        Returns:
            The created position dict
        """
        positions_dir = self._get_positions_dir(username)
        positions_dir.mkdir(parents=True, exist_ok=True)

        # Extract asset from strategy
        asset = strategy_snapshot.get("asset", {})
        if isinstance(asset, dict):
            asset_name = asset.get("primary", "UNKNOWN")
        else:
            asset_name = str(asset)

        # Generate position ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        position_id = f"pos_{timestamp}_{asset_name}"

        # Build entry snapshot (key strategy fields at entry moment)
        entry_snapshot = {
            "strategy_text": strategy_snapshot.get("user_input", {}).get("strategy_text", ""),
            "position_text": strategy_snapshot.get("user_input", {}).get("position_text", ""),
            "target": strategy_snapshot.get("user_input", {}).get("target", ""),
            "stance": strategy_snapshot.get("stance"),
            "position_status": strategy_snapshot.get("position_status"),
            "time_horizon": strategy_snapshot.get("time_horizon"),
            "topics": strategy_snapshot.get("topics"),
            "latest_analysis": strategy_snapshot.get("latest_analysis"),
            "exploration_findings": strategy_snapshot.get("exploration_findings"),
            "dashboard_question": strategy_snapshot.get("dashboard_question"),
        }

        position = {
            "position_id": position_id,
            "strategy_id": strategy_id,
            "username": username,
            "asset": asset_name,
            "direction": direction,
            "stance_at_entry": strategy_snapshot.get("stance"),
            "status": "open",
            "entry": {
                "timestamp": datetime.now().isoformat(),
                "price": entry_price,
                "suggested_by_ai": ai_suggested,
                "ai_confidence": ai_confidence,
                "notes": notes,
            },
            "exit": None,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "performance": None,
            "entry_snapshot": entry_snapshot,
            "exit_snapshot": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # Save position
        position_path = positions_dir / f"{position_id}.json"
        with open(position_path, 'w') as f:
            json.dump(position, f, indent=2)

        return position

    def close_position(
        self,
        username: str,
        position_id: str,
        exit_price: float,
        exit_reason: str,
        strategy_snapshot: Optional[Dict] = None,
        notes: str = "",
    ) -> Optional[Dict]:
        """
        Close an open position and calculate performance.

        Args:
            username: User who owns the position
            position_id: Position ID to close
            exit_price: Price at which position was exited
            exit_reason: "target_reached", "stop_hit", "manual", "ai_suggested"
            strategy_snapshot: Optional current strategy state for exit snapshot
            notes: Optional notes

        Returns:
            The updated position dict, or None if not found/already closed
        """
        position = self.get_position(username, position_id)
        if not position or position["status"] != "open":
            return None

        entry_price = position["entry"]["price"]
        direction = position["direction"]

        # Calculate P&L
        if direction == "long":
            pnl_pips = (exit_price - entry_price) * 10000  # For FX (adjust for other assets)
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # short
            pnl_pips = (entry_price - exit_price) * 10000
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100

        # Determine outcome
        if pnl_percent > 0.1:
            outcome = "win"
        elif pnl_percent < -0.1:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # Calculate duration
        entry_time = datetime.fromisoformat(position["entry"]["timestamp"])
        exit_time = datetime.now()
        duration_days = (exit_time - entry_time).days

        # Update position
        position["exit"] = {
            "timestamp": exit_time.isoformat(),
            "price": exit_price,
            "reason": exit_reason,
            "notes": notes,
        }
        position["status"] = "closed"
        position["performance"] = {
            "pnl_pips": round(pnl_pips, 1),
            "pnl_percent": round(pnl_percent, 2),
            "duration_days": duration_days,
            "outcome": outcome,
        }

        # Add exit snapshot if provided
        if strategy_snapshot:
            position["exit_snapshot"] = {
                "latest_analysis": strategy_snapshot.get("latest_analysis"),
                "exploration_findings": strategy_snapshot.get("exploration_findings"),
            }

        position["updated_at"] = datetime.now().isoformat()

        # Save updated position
        positions_dir = self._get_positions_dir(username)
        position_path = positions_dir / f"{position_id}.json"
        with open(position_path, 'w') as f:
            json.dump(position, f, indent=2)

        return position

    def get_position(self, username: str, position_id: str) -> Optional[Dict]:
        """Get a single position by ID."""
        positions_dir = self._get_positions_dir(username)
        position_path = positions_dir / f"{position_id}.json"

        if not position_path.exists():
            return None

        with open(position_path, 'r') as f:
            return json.load(f)

    def list_positions(
        self,
        username: str,
        status: str = "all",  # "open", "closed", "all"
    ) -> List[Dict]:
        """
        List positions for a user.

        Args:
            username: User to list positions for
            status: Filter by status ("open", "closed", "all")

        Returns:
            List of positions, sorted by created_at descending (newest first)
        """
        positions_dir = self._get_positions_dir(username)
        if not positions_dir.exists():
            return []

        positions = []
        for file_path in positions_dir.glob("pos_*.json"):
            try:
                with open(file_path, 'r') as f:
                    position = json.load(f)
                    if status == "all" or position.get("status") == status:
                        positions.append(position)
            except (json.JSONDecodeError, IOError):
                continue

        # Sort by created_at descending (newest first)
        return sorted(positions, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_portfolio_stats(self, username: str) -> Dict:
        """
        Calculate aggregate portfolio statistics.

        Returns:
            Dict with open_count, closed_count, total_pnl_percent, win_rate, signal_accuracy
        """
        positions = self.list_positions(username, status="all")

        open_positions = [p for p in positions if p.get("status") == "open"]
        closed_positions = [p for p in positions if p.get("status") == "closed"]

        # Calculate closed stats
        total_closed = len(closed_positions)
        wins = len([p for p in closed_positions if p.get("performance", {}).get("outcome") == "win"])
        losses = len([p for p in closed_positions if p.get("performance", {}).get("outcome") == "loss"])

        total_pnl = sum(
            p.get("performance", {}).get("pnl_percent", 0)
            for p in closed_positions
        )

        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        # Signal accuracy (how often AI suggestions were correct)
        ai_suggested = [
            p for p in closed_positions
            if p.get("entry", {}).get("suggested_by_ai")
        ]
        ai_correct = len([
            p for p in ai_suggested
            if p.get("performance", {}).get("outcome") == "win"
        ])
        signal_accuracy = (ai_correct / len(ai_suggested) * 100) if ai_suggested else 0

        return {
            "open_count": len(open_positions),
            "closed_count": total_closed,
            "total_pnl_percent": round(total_pnl, 2),
            "win_rate": round(win_rate, 1),
            "signal_accuracy": round(signal_accuracy, 1),
            "wins": wins,
            "losses": losses,
        }

    def get_position_for_strategy(self, username: str, strategy_id: str) -> Optional[Dict]:
        """
        Get the active (open) position for a strategy, if any.

        Args:
            username: User who owns the position
            strategy_id: Strategy ID to find position for

        Returns:
            The open position for this strategy, or None
        """
        positions = self.list_positions(username, status="open")
        for position in positions:
            if position.get("strategy_id") == strategy_id:
                return position
        return None
