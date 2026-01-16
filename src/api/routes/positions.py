"""Position API Routes - Track actual positions entered/exited by users."""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from src.storage.position_manager import PositionStorageManager
from src.storage.strategy_manager import StrategyStorageManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/positions", tags=["positions"])

position_manager = PositionStorageManager()
strategy_manager = StrategyStorageManager()


# Request/Response Models
class PositionEntryRequest(BaseModel):
    """Request body for creating a new position (entering a trade)."""
    strategy_id: str
    entry_price: float
    direction: str  # "long" or "short"
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: str = ""


class PositionExitRequest(BaseModel):
    """Request body for closing a position (exiting a trade)."""
    exit_price: float
    exit_reason: str  # "target_reached", "stop_hit", "manual", "ai_suggested"
    notes: str = ""


# Routes
@router.get("/{username}")
def list_positions(username: str, status: str = "all"):
    """
    List all positions for a user.

    Args:
        username: User to list positions for
        status: Filter by status ("open", "closed", "all")

    Returns:
        List of positions sorted by created_at (newest first)
    """
    if status not in {"open", "closed", "all"}:
        raise HTTPException(status_code=400, detail="status must be 'open', 'closed', or 'all'")

    positions = position_manager.list_positions(username, status)
    return {"positions": positions, "count": len(positions)}


@router.get("/{username}/stats")
def get_portfolio_stats(username: str):
    """
    Get aggregate portfolio statistics for a user.

    Returns:
        - open_count: Number of open positions
        - closed_count: Number of closed positions
        - total_pnl_percent: Total P&L percentage across all closed positions
        - win_rate: Percentage of winning trades
        - signal_accuracy: Percentage of AI-suggested entries that were wins
        - wins: Number of winning trades
        - losses: Number of losing trades
    """
    stats = position_manager.get_portfolio_stats(username)
    return stats


@router.post("/{username}")
def create_position(username: str, request: PositionEntryRequest):
    """
    Create a new position (enter a trade).

    This:
    1. Gets the full strategy snapshot
    2. Creates a position record with the snapshot
    3. Updates strategy position_status to "in_position"
    4. Links the position to the strategy
    5. Clears the AI signal (it's been acted upon)

    Args:
        username: User creating the position
        request: Entry details (strategy_id, entry_price, direction, etc.)

    Returns:
        The created position
    """
    # Validate direction
    if request.direction not in {"long", "short"}:
        raise HTTPException(status_code=400, detail="direction must be 'long' or 'short'")

    # Get full strategy snapshot
    strategy = strategy_manager.get_strategy(username, request.strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Check if strategy already has an open position
    existing = position_manager.get_position_for_strategy(username, request.strategy_id)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Strategy already has an open position: {existing['position_id']}"
        )

    # Get AI signal info (if entry was AI-suggested)
    signal = strategy.get("suggested_position", {})
    ai_suggested = signal.get("status") == "enter"
    ai_confidence = signal.get("confidence", "medium") if ai_suggested else None

    # Create position
    position = position_manager.create_position(
        username=username,
        strategy_id=request.strategy_id,
        strategy_snapshot=strategy,
        entry_price=request.entry_price,
        direction=request.direction,
        target_price=request.target_price,
        stop_loss=request.stop_loss,
        notes=request.notes,
        ai_suggested=ai_suggested,
        ai_confidence=ai_confidence or "medium",
    )

    # Update strategy: set position_status to "in_position"
    strategy_manager.update_position_status(username, request.strategy_id, "in_position")

    # Link position to strategy
    strategy_manager.set_active_position(username, request.strategy_id, position["position_id"])

    # Clear the signal (mark as acted upon)
    strategy_manager.save_signal(username, request.strategy_id, {
        "status": "hold",
        "confidence": None,
        "reasoning": f"Position entered at {request.entry_price}",
        "key_factors": [],
        "detected_at": None,
        "market_price_at_detection": None,
    })

    logger.info(f"Created position {position['position_id']} for {username}/{request.strategy_id}")

    return position


@router.post("/{username}/{position_id}/close")
def close_position(username: str, position_id: str, request: PositionExitRequest):
    """
    Close an existing position (exit a trade).

    This:
    1. Closes the position and calculates P&L
    2. Updates strategy position_status to "looking_to_enter"
    3. Clears the active position link from strategy

    Args:
        username: User closing the position
        position_id: Position ID to close
        request: Exit details (exit_price, exit_reason, notes)

    Returns:
        The closed position with performance stats
    """
    # Validate exit reason
    valid_reasons = {"target_reached", "stop_hit", "manual", "ai_suggested"}
    if request.exit_reason not in valid_reasons:
        raise HTTPException(
            status_code=400,
            detail=f"exit_reason must be one of: {', '.join(valid_reasons)}"
        )

    # Get position
    position = position_manager.get_position(username, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    if position["status"] != "open":
        raise HTTPException(status_code=400, detail="Position is already closed")

    # Get current strategy snapshot for exit
    strategy = strategy_manager.get_strategy(username, position["strategy_id"])

    # Close position
    closed = position_manager.close_position(
        username=username,
        position_id=position_id,
        exit_price=request.exit_price,
        exit_reason=request.exit_reason,
        strategy_snapshot=strategy,
        notes=request.notes,
    )

    if not closed:
        raise HTTPException(status_code=500, detail="Failed to close position")

    # Update strategy: set position_status back to "looking_to_enter"
    strategy_manager.update_position_status(username, position["strategy_id"], "looking_to_enter")

    # Clear active position link
    strategy_manager.set_active_position(username, position["strategy_id"], None)

    logger.info(f"Closed position {position_id} for {username} with P&L: {closed['performance']['pnl_percent']}%")

    return closed


@router.get("/{username}/{position_id}")
def get_position(username: str, position_id: str):
    """
    Get a single position with full details including entry/exit snapshots.

    Args:
        username: User who owns the position
        position_id: Position ID

    Returns:
        Full position details
    """
    position = position_manager.get_position(username, position_id)
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return position
