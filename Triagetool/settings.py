"""
config/settings.py — All environment-based configuration
"""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    # Azure Bot Framework credentials
    APP_ID: str = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD: str = os.environ.get("MicrosoftAppPassword", "")
    PORT: int = int(os.environ.get("PORT", 3978))

    # ELK / Elasticsearch
    ELK_HOST: str = os.environ.get("ELK_HOST", "https://your-elk-host:9200")
    ELK_API_KEY: str = os.environ.get("ELK_API_KEY", "")
    ELK_INDEX: str = os.environ.get("ELK_INDEX", "logs-*")
    ELK_TIMEOUT: int = int(os.environ.get("ELK_TIMEOUT", 30))

    # Your Refinement Model
    MODEL_API_URL: str = os.environ.get("MODEL_API_URL", "http://localhost:8001/analyze")
    MODEL_API_KEY: str = os.environ.get("MODEL_API_KEY", "")
    MODEL_TIMEOUT: int = int(os.environ.get("MODEL_TIMEOUT", 60))

    # Session TTL in seconds (30 min default)
    SESSION_TTL: int = int(os.environ.get("SESSION_TTL", 1800))

    # Redis (optional — falls back to in-memory if not set)
    REDIS_URL: str = os.environ.get("REDIS_URL", "")
