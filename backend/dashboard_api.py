from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional
from .database import get_async_session
from .models import Doctor, Appointment, LabRequest, Prescription

router = APIRouter()

class DashboardLogin(BaseModel):
    username: str
    password: str
    role: str

@router.post("/login")
async def dashboard_login(creds: DashboardLogin, db: AsyncSession = Depends(get_async_session)):
    if creds.password.strip() != "admin": 
        raise HTTPException(401, "Invalid password")
    
    if creds.role == "doctor":
        # FUZZY MATCHING LOGIC
        # 1. Try exact match
        res = await db.execute(select(Doctor).where(Doctor.name.ilike(f"%{creds.username}%")))
        doc = res.scalars().first()
        
        # 2. Try partial match (e.g. user typed "Sarah" -> finds "Dr. Sarah Smith")
        if not doc:
             res = await db.execute(select(Doctor).where(Doctor.name.ilike(f"%{creds.username.split()[0]}%")))
             doc = res.scalars().first()

        if doc:
            return {"success": True, "id": doc.id, "name": doc.name, "role": "doctor"}
        else:
            return {"success": False, "message": "Doctor not found"}

    return {"success": True, "id": 0, "name": "Staff Member", "role": creds.role}

# --- 1. APPOINTMENTS (With Cancellation Reason) ---
@router.get("/appointments/{user_id}")
async def get_appointments(user_id: int, role: str = "doctor", db: AsyncSession = Depends(get_async_session)):
    query = select(Appointment).options(selectinload(Appointment.patient), selectinload(Appointment.slot)).order_by(Appointment.id.desc())
    if role == "doctor": query = query.where(Appointment.doctor_id == user_id)
    res = await db.execute(query)
    
    return [{
        "id": a.id,
        "patient_name": a.patient.name,
        "patient_id": a.patient.patient_id,
        "time": a.slot.time.strftime("%I:%M %p"),
        "date": a.slot.date.strftime("%Y-%m-%d"),
        "type": a.consultation_mode,
        "reason": a.reason,
        "ai_analysis": a.ai_analysis, # <--- SEND THIS TO FRONTEND
        "status": a.status,
        "cancellation_reason": a.cancellation_reason
    } for a in res.scalars().all()]

@router.patch("/appointments/{appt_id}/status")
async def update_status(appt_id: int, status: str = Body(..., embed=True), reason: Optional[str] = Body(None, embed=True), db: AsyncSession = Depends(get_async_session)):
    appt = await db.get(Appointment, appt_id)
    if not appt: raise HTTPException(404)
    
    appt.status = status
    if status == "Cancelled" and reason:
        appt.cancellation_reason = reason
    elif status != "Cancelled":
        appt.cancellation_reason = None # Clear reason if un-cancelled
        
    db.add(appt)
    await db.commit()
    return {"success": True}

# --- 2. LAB REQUESTS (Real Data) ---
@router.get("/labs")
async def get_labs(db: AsyncSession = Depends(get_async_session)):
    res = await db.execute(select(LabRequest).options(selectinload(LabRequest.patient)).order_by(LabRequest.id.desc()))
    return [{"id": l.id, "patient": l.patient.name, "test": l.test_name, "status": l.status, "date": l.date_requested} for l in res.scalars().all()]

@router.patch("/labs/{lab_id}/status")
async def update_lab_status(lab_id: int, status: str = Body(..., embed=True), db: AsyncSession = Depends(get_async_session)):
    lab = await db.get(LabRequest, lab_id)
    if lab:
        lab.status = status
        db.add(lab)
        await db.commit()
    return {"success": True}

# --- 3. PRESCRIPTIONS (Image & Verification) ---
@router.get("/prescriptions")
async def get_prescriptions(db: AsyncSession = Depends(get_async_session)):
    res = await db.execute(select(Prescription).options(selectinload(Prescription.patient)).order_by(Prescription.id.desc()))
    return [{
        "id": p.id, 
        "patient": p.patient.name, 
        "image_url": f"http://localhost:8000/static/{p.image_path}", # Served via StaticFiles
        "status": p.status, 
        "date": p.created_at.strftime("%Y-%m-%d")
    } for p in res.scalars().all()]

@router.patch("/prescriptions/{pid}/status")
async def update_rx_status(pid: int, status: str = Body(..., embed=True), db: AsyncSession = Depends(get_async_session)):
    rx = await db.get(Prescription, pid)
    if rx:
        rx.status = status
        db.add(rx)
        await db.commit()
    return {"success": True}