# backend/llm_integration.py
import json
import re
import os
from typing import Dict, List, Any

# --- NEW IMPORTS FOR GROQ ---
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("GROQ_MODEL", "llama3-8b-8192")

if not GROQ_API_KEY:
    print("⚠️ WARNING: GROQ_API_KEY not found in .env. LLM features will fail.")

def get_llm():
    """
    Returns the LangChain ChatGroq object for RAG and general use.
    """
    return ChatGroq(
        temperature=0.3,
        model_name=MODEL_NAME,
        api_key=GROQ_API_KEY
    )

# --- 1. SYMPTOM EXTRACTION ---
async def extract_symptoms_from_llm(query: str) -> Dict[str, Any]:
    print(f"LLM (Groq): Extracting symptoms for: {query}")
    
    prompt = """
    You are a medical entity extractor.
    Analyze the user's text. Extract the main symptom and any associated symptoms.
    
    Return ONLY a JSON object with these keys:
    - "main_symptom": string
    - "associated": list of strings
    
    Do NOT add any markdown formatting (like ```json). Just the raw JSON string.
    
    User text: "{query}"
    """
    
    try:
        llm = get_llm()
        # Llama 3 follows instructions well, so we simply ask for JSON
        response = await llm.ainvoke([HumanMessage(content=prompt.format(query=query))])
        txt = response.content
        
        # Clean up potential markdown code blocks
        txt = txt.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(txt)
        return {
            "main_symptom": data.get("main_symptom", query),
            "associated": data.get("associated", [])
        }
    except Exception as e:
        print(f"GROQ EXTRACTION ERROR: {e}")
        return {"main_symptom": query, "associated": []}

# --- 2. PRESCRIPTION VISION SIMULATOR ---
async def simulate_prescription_scan() -> List[Dict[str, str]]:
    """
    Simulates OCR by asking Groq to generate plausible medicine data.
    """
    prompt = """
    Generate a JSON list of 3 realistic medicines for a prescription.
    Each object MUST have: "name", "dosage", "frequency".
    Example: [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "Twice daily"}]
    
    Return ONLY valid JSON. No extra text.
    """
    
    try:
        llm = get_llm()
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        txt = response.content.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(txt)
        if isinstance(data, list):
            return data
        if isinstance(data, dict): 
             # Handle if it wrapped it in a root key
            return list(data.values())[0]
            
        return []
    except Exception as e:
        print(f"GROQ VISION SIM ERROR: {e}")
        # Fallback
        return [
            {"name": "Paracetamol", "dosage": "650mg", "frequency": "SOS"},
            {"name": "Cetirizine", "dosage": "10mg", "frequency": "Nightly"},
            {"name": "Multivitamin", "dosage": "1 tab", "frequency": "Daily"}
        ]

# --- 3. GENERAL QUERY ---
async def query_llm(query: str, patient_id: str = None) -> str:
    try:
        # PROFESSIONAL PROMPT (Fixes Point #1)
        system_prompt = """
        You are an expert AI medical triage assistant.
        Analyze the user's symptoms with clinical precision.
        
        OUTPUT FORMAT:
        **Risk Level:** [Low / Moderate / High / Critical]
        **Clinical Assessment:** [2 sentences explaining the potential condition professionally]
        **Recommended Action:** [1 specific recommendation, e.g., 'Book a GP appointment within 24 hours' or 'Go to ER immediately']
        
        Keep it concise, empathetic, and professional. No disclaimers needed.
        """
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]
        response = await llm.ainvoke(messages)
        return response.content
    except Exception as e:
        print(f"GROQ QUERY ERROR: {e}")
        return "System is currently unable to process complex queries."