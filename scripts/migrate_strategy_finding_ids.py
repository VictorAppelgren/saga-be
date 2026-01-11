"""
Migration Script: Add IDs to Existing Strategy Findings

Scans all strategy JSON files and adds R_XXXXXXXXX or O_XXXXXXXXX IDs
to any findings that don't have them.

Usage:
    cd saga-be
    python scripts/migrate_strategy_finding_ids.py          # Dry run (show what would change)
    python scripts/migrate_strategy_finding_ids.py --fix    # Actually update the files
"""

import os
import sys
import json
import random
import string
import argparse
from pathlib import Path
from typing import Set
from datetime import datetime


def generate_finding_id(mode: str, existing_ids: Set[str]) -> str:
    """Generate a unique finding ID."""
    prefix = "R" if mode == "risk" else "O"
    charset = string.ascii_uppercase + string.digits

    for _ in range(100):
        suffix = ''.join(random.choices(charset, k=9))
        new_id = f"{prefix}_{suffix}"
        if new_id not in existing_ids:
            return new_id

    import time
    return f"{prefix}_{int(time.time())}"


def migrate_findings(users_dir: Path, dry_run: bool = True) -> dict:
    """
    Add IDs to all existing strategy findings that don't have them.

    Args:
        users_dir: Path to users directory
        dry_run: If True, only show what would change without updating

    Returns:
        Stats dict with counts
    """
    stats = {
        "strategies_scanned": 0,
        "strategies_with_findings": 0,
        "risks_updated": 0,
        "opportunities_updated": 0,
        "already_have_ids": 0,
        "errors": 0
    }

    # Collect all existing IDs across all strategies first
    existing_ids: Set[str] = set()

    # First pass: collect existing IDs
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir() or user_dir.name.startswith('.'):
            continue

        for strategy_file in user_dir.glob("strategy_*.json"):
            try:
                with open(strategy_file, 'r') as f:
                    strategy = json.load(f)

                findings = strategy.get("exploration_findings", {})
                for key in ["risks", "opportunities"]:
                    for finding in findings.get(key, []):
                        if finding.get("id"):
                            existing_ids.add(finding["id"])
            except:
                pass

    print(f"Found {len(existing_ids)} existing finding IDs across all strategies")

    # Second pass: add IDs where missing
    for user_dir in users_dir.iterdir():
        if not user_dir.is_dir() or user_dir.name.startswith('.'):
            continue

        username = user_dir.name

        for strategy_file in user_dir.glob("strategy_*.json"):
            stats["strategies_scanned"] += 1

            try:
                with open(strategy_file, 'r') as f:
                    strategy = json.load(f)

                strategy_id = strategy.get("id", strategy_file.stem)
                findings = strategy.get("exploration_findings", {})

                if not findings:
                    continue

                stats["strategies_with_findings"] += 1
                strategy_updated = False

                # Process risks
                for risk in findings.get("risks", []):
                    if not risk.get("id"):
                        new_id = generate_finding_id("risk", existing_ids)
                        existing_ids.add(new_id)
                        risk["id"] = new_id
                        risk["strategy_id"] = strategy_id
                        risk["username"] = username
                        stats["risks_updated"] += 1
                        strategy_updated = True
                        print(f"  [RISK] {username}/{strategy_id}: Added ID {new_id} to '{risk.get('headline', 'N/A')[:50]}'")
                    else:
                        stats["already_have_ids"] += 1

                # Process opportunities
                for opp in findings.get("opportunities", []):
                    if not opp.get("id"):
                        new_id = generate_finding_id("opportunity", existing_ids)
                        existing_ids.add(new_id)
                        opp["id"] = new_id
                        opp["strategy_id"] = strategy_id
                        opp["username"] = username
                        stats["opportunities_updated"] += 1
                        strategy_updated = True
                        print(f"  [OPP]  {username}/{strategy_id}: Added ID {new_id} to '{opp.get('headline', 'N/A')[:50]}'")
                    else:
                        stats["already_have_ids"] += 1

                # Save if updated
                if strategy_updated and not dry_run:
                    strategy["exploration_findings"] = findings
                    strategy["updated_at"] = datetime.now().isoformat()
                    with open(strategy_file, 'w') as f:
                        json.dump(strategy, f, indent=2)

            except json.JSONDecodeError as e:
                print(f"  [ERROR] {strategy_file}: Invalid JSON: {e}")
                stats["errors"] += 1
            except Exception as e:
                print(f"  [ERROR] {strategy_file}: {e}")
                stats["errors"] += 1

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add IDs to existing strategy findings")
    parser.add_argument("--fix", action="store_true", help="Actually update files (default is dry-run)")
    parser.add_argument("--users-dir", default="users", help="Path to users directory")
    args = parser.parse_args()

    users_dir = Path(args.users_dir)
    if not users_dir.exists():
        print(f"Error: Users directory not found: {users_dir}")
        sys.exit(1)

    mode = "UPDATING FILES" if args.fix else "DRY RUN (use --fix to apply)"
    print(f"\n{'='*60}")
    print(f"Strategy Finding ID Migration - {mode}")
    print(f"{'='*60}\n")

    stats = migrate_findings(users_dir, dry_run=not args.fix)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Strategies scanned:     {stats['strategies_scanned']}")
    print(f"  With findings:          {stats['strategies_with_findings']}")
    print(f"  Risks updated:          {stats['risks_updated']}")
    print(f"  Opportunities updated:  {stats['opportunities_updated']}")
    print(f"  Already had IDs:        {stats['already_have_ids']}")
    print(f"  Errors:                 {stats['errors']}")
    print(f"{'='*60}\n")

    if not args.fix and (stats['risks_updated'] > 0 or stats['opportunities_updated'] > 0):
        print("Run with --fix to apply these changes to the files")
