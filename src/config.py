"""
RetailIQ - Configuration Management
NexusTiQ24 Hackathon | Track: PS03 - Retail: Sales and Inventory Copilot

Centralizes all environment variables and configuration paths.
Ensures GEMINI_API_KEY is safely loaded from environment / .env without hardcoding.
"""

import os
from dotenv import load_dotenv

# Project Root Directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env file from project root if it exists
ENV_PATH = os.path.join(BASE_DIR, ".env")
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH)
else:
    load_dotenv()

# Standard project directory paths
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

# Gemini Configuration
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
GEMINI_EMBEDDING_MODEL: str = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001").strip()


def get_gemini_api_key() -> str:
    """Returns the currently loaded GEMINI_API_KEY or empty string."""
    return os.getenv("GEMINI_API_KEY", "").strip()


def is_gemini_configured() -> bool:
    """Checks whether a non-empty, non-placeholder GEMINI_API_KEY is available."""
    key = get_gemini_api_key()
    placeholder_values = {"", "your_gemini_api_key_here", "your_api_key_here", "none"}
    return bool(key and key.lower() not in placeholder_values)
