from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, date, time, timedelta
from urllib.parse import unquote
import shutil
import os
import requests 
import base64

# --- IMPORTS ---
from .database import get_async_session
from . import models as db_models
from . import schemas as api_schemas
from dotenv import load_dotenv

load_dotenv() 

router = APIRouter()

# =========================================================================
# ZOOM API HELPER
# =========================================================================
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")

def generate_zoom_link(topic: str, start_time: str):
    if not (ZOOM_ACCOUNT_ID and ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET):
        return "https://zoom.us/j/demo_link_creds_missing"
    try:
        url = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={ZOOM_ACCOUNT_ID}"
        auth_str = f"{ZOOM_CLIENT_ID}:{ZOOM_CLIENT_SECRET}"
        b64_auth = base64.b64encode(auth_str.encode()).decode()
        headers = {"Authorization": f"Basic {b64_auth}"}
        resp = requests.post(url, headers=headers)
        if resp.status_code != 200: return None
        access_token = resp.json().get("access_token")

        create_url = "https://api.zoom.us/v2/users/me/meetings"
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        payload = {"topic": topic, "type": 2, "start_time": start_time, "duration": 30}
        meet_resp = requests.post(create_url, headers=headers, json=payload)
        return meet_resp.json().get("join_url") if meet_resp.status_code == 201 else None
    except: return None

# =========================================================================
# 1. DOCTORS (REMOVED JOHN DOE)
# =========================================================================
@router.get("/appointments/doctors", response_model=List[api_schemas.Doctor])
async def get_all_doctors(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(db_models.Doctor))
    all_docs = result.scalars().all()
    # FILTER: Remove John Doe
    return [d for d in all_docs if "John Doe" not in d.name and "Doe" not in d.name]

@router.get("/appointments/doctors/{specialty}", response_model=List[api_schemas.Doctor])
async def get_doctors_by_specialty(specialty: str, session: AsyncSession = Depends(get_async_session)):
    clean_spec = unquote(specialty)
    result = await session.execute(select(db_models.Doctor).where(db_models.Doctor.specialty.ilike(f"%{clean_spec}%")))
    docs = result.scalars().all() or (await session.execute(select(db_models.Doctor))).scalars().all()
    # FILTER: Remove John Doe
    return [d for d in docs if "John Doe" not in d.name and "Doe" not in d.name]

# =========================================================================
# 2. AVAILABILITY
# =========================================================================
@router.get("/appointments/availability/{doctor_id}/{date_str}", response_model=api_schemas.AvailabilityCheckResponse)
async def get_doctor_availability(doctor_id: int, date_str: str, session: AsyncSession = Depends(get_async_session)):
    try:
        request_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    doctor = await session.get(db_models.Doctor, doctor_id)
    if not doctor:
        res = await session.execute(select(db_models.Doctor))
        doctor = res.scalars().first()
        if not doctor: raise HTTPException(status_code=404, detail="Doctor not found")

    res = await session.execute(select(db_models.AvailabilitySlot).where(
        db_models.AvailabilitySlot.doctor_id == doctor.id,
        db_models.AvailabilitySlot.date == request_date,
        db_models.AvailabilitySlot.is_booked == False
    ))
    slots = [s.time for s in res.scalars().all()]
    return api_schemas.AvailabilityCheckResponse(doctor=doctor, available_slots=slots)

# =========================================================================
# 3. BOOKING (Updated to avoid John Doe & Strict ID)
# =========================================================================
@router.post("/appointments/book", status_code=201)
async def book_appointment(payload: dict = Body(...), session: AsyncSession = Depends(get_async_session)):
    print(f"DEBUG: Booking -> {payload}")
    try:
        pid, doc_id = payload.get("patient_id"), payload.get("doctor_id")
        date_str, time_str = payload.get("date"), payload.get("time")
        mode = payload.get("consultation_mode", "In-Person")

        # Patient
        res = await session.execute(select(db_models.Patient).where(db_models.Patient.patient_id == pid))
        patient = res.scalars().first()
        if not patient:
            patient = db_models.Patient(patient_id=pid, name="Guest User", email=f"{pid}@guest.com", phone="000", age=0, gender="U")
            session.add(patient); await session.flush()

        # Doctor - STRICT CHECK (No fallback to Sarah Smith)
        doctor = await session.get(db_models.Doctor, doc_id)
        if not doctor:
            # If the ID sent by Rasa is invalid, fail loudly so we can fix Rasa mapping
            raise HTTPException(404, f"Doctor ID {doc_id} not found in database.")

        # Slot
        appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        appt_time = datetime.strptime(str(time_str).strip()[:5] + ":00", "%H:%M:%S").time()
        
        res = await session.execute(select(db_models.AvailabilitySlot).where(
            db_models.AvailabilitySlot.doctor_id == doc_id, db_models.AvailabilitySlot.date == appt_date, db_models.AvailabilitySlot.time == appt_time
        ))
        slot = res.scalars().first()
        if not slot:
            slot = db_models.AvailabilitySlot(doctor_id=doc_id, date=appt_date, time=appt_time, is_booked=True)
            session.add(slot); await session.flush()
        else: slot.is_booked = True

        # Zoom
        zoom_url = None
        if "Video" in mode:
            iso = f"{appt_date}T{appt_time}Z"
            zoom_url = generate_zoom_link(f"Dr. {doctor.name}", iso)

        # Save
        new_appt = db_models.Appointment(
            patient_id=patient.id, doctor_id=doc_id, slot_id=slot.id, 
            reason=payload.get("reason"), consultation_mode=mode, meeting_link=zoom_url, status="Scheduled"
        )
        session.add(new_appt); await session.commit()
        return {"message": "Booked", "meeting_link": zoom_url}
    except Exception as e:
        print(f"ERROR: {e}")
        raise HTTPException(500, str(e))

# =========================================================================
# 4. LAB & UPLOAD (Fixed Upload Logic)
# =========================================================================
from pydantic import BaseModel
class LabBooking(BaseModel):
    patient_id: str
    test_name: str

@router.post("/appointments/book_lab")
async def book_lab_test(payload: LabBooking, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(db_models.Patient).where(db_models.Patient.patient_id == payload.patient_id))
    patient = res.scalars().first()
    if not patient: raise HTTPException(404, "Patient not found.")
    new_lab = db_models.LabRequest(patient_id=patient.id, test_name=payload.test_name, status="Scheduled", date_requested=date.today())
    session.add(new_lab); await session.commit()
    return {"message": "Lab Scheduled", "id": new_lab.id}

@router.post("/appointments/upload_prescription")
async def upload_prescription(patient_id: str = Body(...), file: UploadFile = File(...), session: AsyncSession = Depends(get_async_session)):
    # 1. Find Patient
    res = await session.execute(select(db_models.Patient).where(db_models.Patient.patient_id == patient_id))
    patient = res.scalars().first()
    
    # 2. Auto-create Guest if missing (crucial for "Guest" uploads)
    if not patient:
        patient = db_models.Patient(patient_id=patient_id, name="Guest", email=f"{patient_id}@guest.com", phone="000", age=0, gender="U")
        session.add(patient); await session.flush()

    # 3. Save File
    if not os.path.exists("uploads"): os.makedirs("uploads")
    file_path = f"uploads/{file.filename}"
    with open(file_path, "wb+") as f: shutil.copyfileobj(file.file, f)

    # 4. Create DB Entry
    new_rx = db_models.Prescription(
        patient_id=patient.id, 
        image_filename=file.filename, 
        status="Uploaded"
    )
    session.add(new_rx); await session.commit()
    return {"message": "Uploaded"}

# =========================================================================
# 5. CONSOLIDATED STATUS
# =========================================================================
@router.get("/appointments/status/{patient_id}")
async def get_patient_status(patient_id: str, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(db_models.Patient).where(db_models.Patient.patient_id == patient_id))
    p = res.scalars().first()
    if not p: return {"records": []}

    # Appointments
    a_res = await session.execute(select(db_models.Appointment).where(db_models.Appointment.patient_id == p.id).options(selectinload(db_models.Appointment.doctor), selectinload(db_models.Appointment.slot)).order_by(db_models.Appointment.id.desc()))
    appts = []
    for a in a_res.scalars().all():
        doc_name = a.doctor.name if a.doctor else "Doctor"
        clean_doc = doc_name.replace("Dr. ", "").replace("Dr.", "").strip()
        appts.append({
            "type": "Appointment",
            "detail": f"Dr. {clean_doc} ({a.reason})",
            "date": a.slot.date.strftime("%Y-%m-%d") if a.slot else "TBD",
            "time": a.slot.time.strftime("%H:%M") if a.slot else "-",
            "status": a.status,
            "link": a.meeting_link
        })

    # Labs
    l_res = await session.execute(select(db_models.LabRequest).where(db_models.LabRequest.patient_id == p.id))
    labs = [{"type": "Lab Test", "detail": l.test_name, "date": l.date_requested.strftime("%Y-%m-%d"), "status": l.status} for l in l_res.scalars().all()]

    # Meds
    p_res = await session.execute(select(db_models.Prescription).where(db_models.Prescription.patient_id == p.id))
    meds = [{"type": "Medicine Order", "detail": p.image_filename, "date": p.created_at.strftime("%Y-%m-%d"), "status": p.status} for p in p_res.scalars().all()]

    return {"records": appts + labs + meds}

# =========================================================================
# 6. OTC ORDER
# =========================================================================
@router.post("/pharmacy/order_otc")
async def order_otc_medicines(payload: dict = Body(...), session: AsyncSession = Depends(get_async_session)):
    try:
        pid = payload.get("patient_id")
        res = await session.execute(select(db_models.Patient).where(db_models.Patient.patient_id == pid))
        p = res.scalars().first()
        if not p:
            p = db_models.Patient(patient_id=pid, name="Guest", email=f"{pid}@g.com", phone="0", age=0, gender="U")
            session.add(p); await session.flush()
        
        order = db_models.Prescription(patient_id=p.id, image_filename="OTC Medicines Kit", status="Ordered")
        session.add(order); await session.commit()
        return {"message": "OTC Ordered"}
    except Exception as e:
        raise HTTPException(500, str(e))

# =========================================================================
# 7. DASHBOARDS
# =========================================================================
@router.get("/appointments/dashboard/doctor/{doctor_id}")
async def get_doctor_dashboard(doctor_id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(db_models.Appointment).where(db_models.Appointment.doctor_id == doctor_id).options(selectinload(db_models.Appointment.patient), selectinload(db_models.Appointment.slot)).order_by(db_models.Appointment.id.desc()))
    records = []
    for a in res.scalars().all():
        p_name = a.patient.name if a.patient else "Guest"
        p_id = a.patient.patient_id if a.patient else "N/A"
        records.append({
            "id": a.id, "type": "Appointment", "title": f"{p_name} ({p_id})", 
            "subtitle": f"Reason: {a.reason}", "date": a.slot.date.strftime("%Y-%m-%d"), 
            "time": a.slot.time.strftime("%H:%M"), "status": a.status, "extra": a.consultation_mode
        })
    
    # FETCH DOCTOR NAME FOR ROLE DISPLAY
    doctor = await session.get(db_models.Doctor, doctor_id)
    doc_name = doctor.name.replace("Dr. ", "").replace("Dr.", "").strip() if doctor else "Doctor"
    
    return {"records": records, "role": f"Dr. {doc_name}"}

@router.get("/appointments/dashboard/lab")
async def get_lab_dashboard(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(db_models.LabRequest).options(selectinload(db_models.LabRequest.patient)).order_by(db_models.LabRequest.id.desc()))
    records = [{"id": l.id, "type": "Lab Test", "title": l.patient.name, "subtitle": l.test_name, "date": str(l.date_requested), "status": l.status} for l in res.scalars().all()]
    return {"records": records, "role": "Central Lab"}

@router.get("/appointments/dashboard/pharmacy")
async def get_pharmacy_dashboard(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(db_models.Prescription).options(selectinload(db_models.Prescription.patient)).order_by(db_models.Prescription.id.desc()))
    records = [{"id": p.id, "type": "Pharmacy", "title": p.patient.name, "subtitle": p.image_filename, "date": str(p.created_at), "status": p.status} for p in res.scalars().all()]
    return {"records": records, "role": "Pharmacy"}

@router.put("/appointments/update/appointment/{appt_id}")
async def update_appt_status(appt_id: int, status: str = Body(..., embed=True), session: AsyncSession = Depends(get_async_session)):
    appt = await session.get(db_models.Appointment, appt_id)
    if appt: appt.status = status; await session.commit()
    return {"message": "Updated"}

@router.put("/appointments/update/lab/{id}")
async def update_lab_status(id: int, status: str = Body(..., embed=True), session: AsyncSession = Depends(get_async_session)):
    item = await session.get(db_models.LabRequest, id)
    if item: item.status = status; await session.commit()
    return {"message": "Updated"}

@router.put("/appointments/update/pharmacy/{id}")
async def update_pharmacy_status(id: int, status: str = Body(..., embed=True), session: AsyncSession = Depends(get_async_session)):
    item = await session.get(db_models.Prescription, id)
    if item: item.status = status; await session.commit()
    return {"message": "Updated"}