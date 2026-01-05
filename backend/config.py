# backend/config.py
import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# --- UPDATED: Make Ollama Optional ---
# We provide a default so it doesn't crash, even if you aren't using it.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434") 

RASA_CORE_URL = os.getenv("RASA_CORE_URL")

# --- Groq Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq") # Default to groq

ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")

TZ_NAME = os.getenv("TZ", "UTC") 
try:
    SERVER_TIMEZONE = ZoneInfo(TZ_NAME)
except Exception:
    print(f"WARNING: Invalid TZ name '{TZ_NAME}'. Defaulting to UTC.")
    SERVER_TIMEZONE = ZoneInfo("UTC")

if not DATABASE_URL:
    raise ValueError("No DATABASE_URL set in .env")

if not RASA_CORE_URL:
    raise ValueError("No RASA_CORE_URL set in .env")

# Ensure Groq Key is present if using Groq
if LLM_PROVIDER == "groq" and not GROQ_API_KEY:
    print("WARNING: LLM_PROVIDER is 'groq' but GROQ_API_KEY is missing in .env")

# --- ADD THIS CHECK ---
if not ZOOM_ACCOUNT_ID or not ZOOM_CLIENT_ID or not ZOOM_CLIENT_SECRET:
    print("WARNING: ZOOM API keys not set. Video links will fail.")