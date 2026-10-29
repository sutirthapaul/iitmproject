"""Central configuration. Everything tunable lives here, not in business logic."""
from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
SAMPLE_DIR = ROOT_DIR / "sample_rfps"

# SQLite file. On Streamlit Community Cloud the filesystem is ephemeral, so the
# database is (re)created and seeded automatically on startup.
DB_PATH = Path(os.environ.get("RFP_DB_PATH", DATA_DIR / "rfp.db"))

# PDF extraction
MAX_DOCUMENT_CHARS = 20_000      # text sent to the LLM per supplier (truncated beyond this)
MIN_DOCUMENT_CHARS = 200         # below this the PDF is treated as unreadable / scanned

# Supplier metadata rules
EXPERIENCE_MIN = 1.0
EXPERIENCE_MAX = 5.0

# Validation
LOW_CONFIDENCE_THRESHOLD = 0.30  # >30% of criteria normalised => scorecard flagged low-confidence
WEIGHT_TOTAL = 100.0
WEIGHT_TOLERANCE = 0.01

# Ranking: mandatory order from the problem statement
RANKING_MODES = {
    "ppi_first": "Higher PPI → earlier submission date → higher experience → supplier name (A-Z)",
}
DEFAULT_RANKING_MODE = "ppi_first"
SORT_PRECISION = 2               # values are rounded to this many decimals before sorting

# LLM providers. All three expose an OpenAI-compatible Chat Completions API,
# so a single client covers them. Model names can be overridden in secrets.
LLM_PROVIDERS = {
    "Mock (no API key)": {"key": None, "base_url": None, "default_model": "mock-keyword-v1"},
    "OpenAI": {
        "key": "OPENAI_API_KEY",
        "base_url": None,
        "default_model": "gpt-4o-mini",
    },
    "Groq": {
        "key": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
    },
    "Google Gemini": {
        "key": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.5-flash",
    },
}
LLM_TEMPERATURE = 0.0
LLM_TIMEOUT_SECONDS = 90
LLM_MAX_RETRIES = 1              # extra attempts after the first call if JSON is unusable
