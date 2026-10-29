"""Domain models shared by agents, tools, persistence and UI."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class Criterion(BaseModel):
    criterion_id: int
    name: str
    description: str
    weight: float
    max_score: int = 10
    is_active: bool = True


class SupplierInput(BaseModel):
    supplier_name: str
    submission_date: date
    experience_rating: float
    file_name: str
    file_bytes: bytes = Field(repr=False)


class ExtractionResult(BaseModel):
    ok: bool
    text: str = ""
    pages: int = 0
    chars: int = 0
    truncated: bool = False
    warnings: list[str] = []
    error: Optional[str] = None


# ---- what the LLM is asked to return (used for the prompt schema and validation)
class LLMCriterionResult(BaseModel):
    criterion_id: int
    score: float
    max_score: int
    justification: str
    evidence: str


class LLMScorecard(BaseModel):
    supplier_name: str
    criteria: list[LLMCriterionResult]
    risks: list[str] = []
    overall_summary: str = ""


# ---- after validation / normalisation
class ValidatedCriterion(BaseModel):
    criterion_id: int
    name: str
    weight: float
    max_score: int
    score: float
    justification: str
    evidence: str
    evidence_verified: bool = False
    normalized: bool = False
    notes: list[str] = []


class ValidatedScorecard(BaseModel):
    supplier_name: str
    criteria: list[ValidatedCriterion]
    risks: list[str] = []
    overall_summary: str = ""
    warnings: list[str] = []
    llm_status: str = "ok"          # ok | repaired | failed | skipped_no_text
    low_confidence: bool = False
