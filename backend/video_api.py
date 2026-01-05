# backend/video_api.py
from fastapi import APIRouter, HTTPException
import httpx
import os
import base64
import time
from dotenv import load_dotenv

load_dotenv()

# --- Initialize Router (This was missing) ---
router = APIRouter()

# --- Configuration ---
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API_URL = "https://api.zoom.us/v2"

# --- Helper: Get Access Token ---
async def get_zoom_access_token():
    if not all([ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET]):
        print("ZOOM_API: Credentials missing. Skipping.")
        return None

    auth_str = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
    b64_auth = base64.b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "account_credentials",
        "account_id": ZOOM_ACCOUNT_ID
    }

    async with httpx.AsyncClient() as client:
        try:
            print("ZOOM_API: Generating new access token...")
            resp = await client.post(ZOOM_TOKEN_URL, headers=headers, data=data)
            resp.raise_for_status()
            token = resp.json().get("access_token")
            print("ZOOM_API: Successfully generated new token.")
            return token
        except Exception as e:
            print(f"ZOOM_API Error: Failed to get token. {e}")
            return None

# --- Internal Function: Create Link ---
async def create_video_call_link(topic: str, start_time: str):
    """
    Creates a Zoom meeting link.
    start_time format: "2024-12-25T10:00:00Z"
    """
    token = await get_zoom_access_token()
    if not token:
        # Fallback if Zoom fails or isn't configured
        return "https://meet.google.com/new" 

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "topic": topic,
        "type": 2, # Scheduled meeting
        "start_time": start_time,
        "duration": 30, 
        "timezone": "UTC",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": True
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{ZOOM_API_URL}/users/me/meetings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            join_url = data.get("join_url")
            print(f"ZOOM_API: Successfully created meeting: {join_url}")
            return join_url
        except Exception as e:
            print(f"ZOOM_API Create Meeting Error: {e}")
            return "https://meet.google.com/new" # Fallback

# --- Endpoint (Optional, if you want to test via API) ---
@router.post("/create_meeting")
async def create_meeting_endpoint(topic: str = "Consultation"):
    link = await create_video_call_link(topic, "2024-01-01T10:00:00Z")
    return {"join_url": link}