from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from typing import Optional
import random

from .database import get_async_session
from .models import Patient

router = APIRouter()

class PatientCreate(BaseModel):
    name: str
    email: str
    age: int
    gender: str
    phone: Optional[str] = "0000000000"
    health_conditions: Optional[str] = "None"

@router.post("/patients")
async def create_patient(patient: PatientCreate, db: AsyncSession = Depends(get_async_session)):
    # Check if email exists first
    existing = await db.execute(select(Patient).where(Patient.email == patient.email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Email already registered")

    try:
        pid = f"PID-{random.randint(10000, 99999)}"
        new_patient = Patient(
            patient_id=pid,
            name=patient.name,
            email=patient.email,
            age=patient.age,
            gender=patient.gender,
            phone=patient.phone,
            health_conditions=patient.health_conditions
        )
        db.add(new_patient)
        await db.commit()
        await db.refresh(new_patient)
        
        # FIX: Return 'name' so Rasa doesn't crash
        return {"success": True, "patient_id": pid, "name": new_patient.name} 

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/patients/lookup")
async def lookup_patient(email: str, db: AsyncSession = Depends(get_async_session)):
    result = await db.execute(select(Patient).where(Patient.email == email))
    patient = result.scalars().first()
    
    if patient:
        return {"success": True, "patient_id": patient.patient_id, "name": patient.name}
    else:
        raise HTTPException(status_code=404, detail="Email not found")