# backend/knowledge_api.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import asyncio
from typing import List

from .llm_integration import query_llm 
from .rag_integration import query_rag # This is now async
from .schemas import KnowledgeQueryRequest

router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base (RAG & LLM)"]
)

class KnowledgeQueryResponse(BaseModel):
    query: str
    response: str
    sources: List[str] = []

@router.post("/llm", response_model=KnowledgeQueryResponse)
async def handle_llm_query(request: KnowledgeQueryRequest):
    """
    Endpoint for general LLM queries.
    """
    try:
        response_text = await query_llm(request.query, request.patient_id)
        return KnowledgeQueryResponse(
            query=request.query,
            response=response_text
        )
    except Exception as e:
        print(f"LLM API Error: {e}")
        raise HTTPException(status_code=500, detail="Error processing LLM query.")

@router.post("/rag", response_model=KnowledgeQueryResponse)
async def handle_rag_query(request: KnowledgeQueryRequest):
    """
    Endpoint for RAG queries.
    --- FIX: Now correctly awaits the async hybrid RAG function ---
    """
    try:
        # FIX: Removed loop.run_in_executor because query_rag is now async
        rag_result = await query_rag(request.query)
        
        return KnowledgeQueryResponse(
            query=request.query,
            response=rag_result.get("answer", "No answer found."),
            sources=rag_result.get("sources", [])
        )
    except Exception as e:
        print(f"RAG API Error: {e}")
        raise HTTPException(status_code=500, detail="Error processing RAG query.")