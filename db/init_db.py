"""Create the SQLite database and seed the sample evaluation criteria.

Usage:
    python -m db.init_db            # create + seed if empty
    python -m db.init_db --reset    # restore the five default criteria
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402
from db import database  # noqa: E402


def main() -> None:
    database.init_db()
    if "--reset" in sys.argv:
        database.reset_criteria()
        print("Criteria reset to defaults.")
    rows = database.get_criteria(active_only=False)
    print(f"Database: {config.DB_PATH}")
    print(f"{'ID':<4}{'Criterion':<26}{'Weight':>8}{'Max':>6}{'Active':>8}")
    for r in rows:
        print(f"{r['criterion_id']:<4}{r['name']:<26}{r['weight']:>7.0f}%{r['max_score']:>6}{r['is_active']:>8}")
    total = sum(r["weight"] for r in rows if r["is_active"])
    print(f"Active weight total: {total:.0f}%")


if __name__ == "__main__":
    main()
