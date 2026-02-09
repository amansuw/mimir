"""
Configuration settings for Jira Review Extractor.
Loads environment variables from .env file.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Jira Configuration
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_USERNAME = os.getenv("JIRA_USERNAME", "")

# Date Range
START_DATE = os.getenv("START_DATE", "2025-01-01")
END_DATE = os.getenv("END_DATE", "")  # Empty means "now"

# Groq LLM Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL_QUICK = os.getenv("GROQ_MODEL_QUICK", "llama-3.1-8b-instant")
GROQ_MODEL_FULL = os.getenv("GROQ_MODEL_FULL", "llama-3.3-70b-versatile")

# Output directories
OUTPUT_DIR = Path("output")
RAW_DIR = OUTPUT_DIR / "raw"
NORMALIZED_DIR = OUTPUT_DIR / "normalized"
SUMMARIES_DIR = OUTPUT_DIR / "summaries"

# Statuses to exclude from summarization (incomplete work)
EXCLUDED_STATUSES = ["Open", "Waiting for support", "To Do", "Backlog"]
