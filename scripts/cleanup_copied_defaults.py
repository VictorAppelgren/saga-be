"""
Cleanup Copied Default Strategies

Now that we load default strategies dynamically from admin (Victor),
we need to remove the old copies that were previously made to all users.

This script:
1. Finds all default strategies (is_default=True in Victor's folder)
2. Removes copies of those strategies from other users' folders

Usage:
    python scripts/cleanup_copied_defaults.py --dry-run   # Preview
    python scripts/cleanup_copied_defaults.py --execute   # Actually delete

Run from saga-be directory.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.strategy_manager import StrategyStorageManager


def find_default_strategy_ids(storage: StrategyStorageManager) -> list[str]:
    """Find all default strategy IDs from admin account."""
    admin_dir = storage.users_dir / storage.DEFAULT_STRATEGY_OWNER
    if not admin_dir.exists():
        print(f"Admin directory not found: {admin_dir}")
        return []

    default_ids = []
    for file_path in admin_dir.glob("strategy_*.json"):
        try:
            with open(file_path, 'r') as f:
                strategy = json.load(f)
                if strategy.get("is_default", False):
                    default_ids.append(strategy["id"])
        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    return default_ids


def find_copies_to_remove(storage: StrategyStorageManager, default_ids: list[str]) -> list[tuple[str, str, Path]]:
    """
    Find all copies of default strategies in other users' folders.
    Returns list of (username, strategy_id, file_path) tuples.
    """
    copies = []
    users = storage.list_users()

    for username in users:
        if username == storage.DEFAULT_STRATEGY_OWNER:
            continue  # Skip admin

        user_dir = storage.users_dir / username
        if not user_dir.exists():
            continue

        for strategy_id in default_ids:
            strategy_path = user_dir / f"{strategy_id}.json"
            if strategy_path.exists():
                copies.append((username, strategy_id, strategy_path))

    return copies


def run_cleanup(dry_run: bool = True):
    """Run the cleanup process."""
    storage = StrategyStorageManager()

    print("\n" + "=" * 60)
    print("  CLEANUP COPIED DEFAULT STRATEGIES")
    print(f"  Mode: {'DRY-RUN (preview)' if dry_run else 'EXECUTE (live)'}")
    print(f"  Admin account: {storage.DEFAULT_STRATEGY_OWNER}")
    print("=" * 60)

    # Step 1: Find default strategy IDs
    print("\n[STEP 1] Finding default strategies...")
    default_ids = find_default_strategy_ids(storage)
    print(f"  Found {len(default_ids)} default strategies:")
    for sid in default_ids:
        print(f"    - {sid}")

    if not default_ids:
        print("\n  No default strategies found. Nothing to clean up.")
        return

    # Step 2: Find copies in other users
    print("\n[STEP 2] Finding copies in user folders...")
    copies = find_copies_to_remove(storage, default_ids)
    print(f"  Found {len(copies)} copies to remove:")

    # Group by user for cleaner output
    by_user = {}
    for username, strategy_id, path in copies:
        if username not in by_user:
            by_user[username] = []
        by_user[username].append((strategy_id, path))

    for username, strategies in by_user.items():
        print(f"    {username}: {len(strategies)} copies")
        for sid, path in strategies[:3]:  # Show first 3
            print(f"      - {sid}")
        if len(strategies) > 3:
            print(f"      ... and {len(strategies) - 3} more")

    if not copies:
        print("\n  No copies found. Nothing to clean up.")
        return

    # Step 3: Remove copies
    print(f"\n[STEP 3] {'Would remove' if dry_run else 'Removing'} {len(copies)} copies...")

    removed = 0
    errors = 0
    for username, strategy_id, path in copies:
        if dry_run:
            print(f"  [DRY-RUN] Would delete: {path}")
            removed += 1
        else:
            try:
                path.unlink()
                removed += 1
                print(f"  Deleted: {path.name} from {username}")
            except Exception as e:
                errors += 1
                print(f"  ERROR deleting {path}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print(f"  Summary:")
    print(f"    Default strategies: {len(default_ids)}")
    print(f"    Copies found:       {len(copies)}")
    print(f"    {'Would remove' if dry_run else 'Removed'}:        {removed}")
    if errors:
        print(f"    Errors:             {errors}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up copied default strategies")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    parser.add_argument("--execute", action="store_true", help="Actually delete copies")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("ERROR: Must specify --dry-run or --execute")
        print("  --dry-run: Preview what would be deleted")
        print("  --execute: Actually delete copies")
        sys.exit(1)

    run_cleanup(dry_run=args.dry_run)
