# backend/rasa_proxy.py
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx

# --- [START] SECURITY FIX ---
from .config import RASA_CORE_URL
# --- [END] SECURITY FIX ---

router = APIRouter()
RASA_TIMEOUT = 30.0  # 30-second timeout

@router.post("/chat")
async def proxy_rasa_chat(request: Request):
    """
    Proxies chat messages from the frontend to the Rasa Core server.
    This is what your index.html talks to.
    """
    body = await request.json()
    
    async with httpx.AsyncClient(timeout=RASA_TIMEOUT) as client:
        try:
            response = await client.post(
                RASA_CORE_URL, # Use the secure URL
                json=body
            )
            response.raise_for_status()
            return JSONResponse(content=response.json(), status_code=response.status_code)
        
        except httpx.ConnectError:
            print(f"Rasa Proxy Error: Cannot connect to Rasa Core at {RASA_CORE_URL}.")
            raise HTTPException(
                status_code=503, 
                detail=f"Cannot connect to Rasa Core server."
            )
        except httpx.HTTPStatusError as e:
            print(f"Rasa Proxy Error: {e.response.status_code} - {e.response.text}")
            raise HTTPException(
                status_code=e.response.status_code, 
                detail=e.response.json()
            )
        except Exception as e:
            print(f"Rasa Proxy Error: An unexpected error occurred: {e}")
            raise HTTPException(status_code=500, detail="Internal proxy error")