# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import engine, AsyncSessionLocal
from .models import Base
from .utils import create_initial_data  # <--- IMPORT THIS

# --- IMPORT MODULES ---
from . import (
    patient_api, 
    appointment_api, 
    knowledge_api, 
    video_api, 
    dashboard_api,
    rasa_proxy
)

import asyncio

async def init_db():
    async with engine.begin() as conn:
        # --- RESET LOGIC (Keep this enabled for ONE run, then comment it out) ---
        # print("DATABASE: Resetting all tables...")
        # await conn.run_sync(Base.metadata.drop_all)
        
        # Create Tables
        await conn.run_sync(Base.metadata.create_all)
        print("DATABASE: Tables recreated successfully.")

    # --- POPULATE DATA ---
    # We open a new session to run the population script
    async with AsyncSessionLocal() as session:
        await create_initial_data(session)

app = FastAPI()

# --- MOUNT STATIC FILES ---
import os
if not os.path.exists("uploads"):
    os.makedirs("uploads")
app.mount("/static", StaticFiles(directory="uploads"), name="static")

# --- CORS SETTINGS ---
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTER ROUTERS ---
app.include_router(patient_api.router)
app.include_router(appointment_api.router)
app.include_router(knowledge_api.router)
app.include_router(video_api.router)
app.include_router(dashboard_api.router, prefix="/dashboard", tags=["Dashboard"])
app.include_router(rasa_proxy.router)

@app.on_event("startup")
async def on_startup():
    await init_db()

@app.get("/")
def read_root():
    return {"message": "Healthcare Chatbot Backend is Running"}