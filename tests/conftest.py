import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import database  # noqa: E402
from domain.models import ValidatedCriterion, ValidatedScorecard  # noqa: E402

CRITERIA = [
    {"criterion_id": 1, "name": "Technical Capability", "description": "tech", "weight": 30, "max_score": 10},
    {"criterion_id": 2, "name": "Implementation Plan", "description": "plan", "weight": 20, "max_score": 10},
    {"criterion_id": 3, "name": "Commercial Value", "description": "price", "weight": 20, "max_score": 10},
    {"criterion_id": 4, "name": "Security & Compliance", "description": "sec", "weight": 20, "max_score": 10},
    {"criterion_id": 5, "name": "Support & Experience", "description": "support", "weight": 10, "max_score": 10},
]


def make_card(name: str, scores: list[float], criteria=CRITERIA) -> ValidatedScorecard:
    return ValidatedScorecard(
        supplier_name=name,
        criteria=[ValidatedCriterion(criterion_id=c["criterion_id"], name=c["name"], weight=c["weight"],
                                     max_score=c["max_score"], score=s, justification="j", evidence="e")
                  for c, s in zip(criteria, scores)])


@pytest.fixture
def criteria():
    return [dict(c) for c in CRITERIA]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    database.init_db(path)
    return path
