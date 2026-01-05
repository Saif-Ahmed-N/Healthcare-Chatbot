# backend/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import List, Optional
from datetime import date, time

# --- Base Configuration ---
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True) # Pydantic v2 "orm_mode"

# --- Patient Schemas ---
class PatientCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    
    # --- NEW FIELDS ---
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    health_conditions: Optional[str] = None

class Patient(BaseSchema):
    id: int
    patient_id: str
    name: str
    email: EmailStr
    phone: str
    
    # --- NEW FIELDS ---
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    health_conditions: Optional[str] = None

class PatientPublic(BaseModel):
    """Data returned to the user after login or registration."""
    patient_id: str
    name: str
    email: EmailStr

# --- Doctor & Availability Schemas ---
class Doctor(BaseSchema):
    id: int
    name: str
    specialty: str

class AvailabilitySlot(BaseSchema):
    id: int
    date: date
    time: time
    is_booked: bool

class AvailabilityCheckResponse(BaseModel):
    doctor: Doctor
    available_slots: List[time] # List of available times for the given date

# --- Appointment Schemas ---
class AppointmentBase(BaseModel):
    reason: str
    doctor_id: int
    date: date
    
    # --- NEW FIELD ---
    consultation_mode: Optional[str] = None

class AppointmentCreate(AppointmentBase):
    """Schema used to request a new appointment."""
    patient_id: str # The public-facing patient ID
    time: time # The specific time slot requested

class Appointment(BaseSchema):
    """Full appointment details for API responses."""
    id: int
    reason: str
    status: str
    
    # --- NEW FIELD ---
    consultation_mode: Optional[str] = None
    
    patient: PatientPublic # Nested patient details
    doctor: Doctor # Nested doctor details
    slot: AvailabilitySlot # Nested slot details

# --- Rasa Action & Query Schemas ---
class RasaActionCall(BaseModel):
    """The webhook payload Rasa sends to our action server."""
    next_action: str
    tracker: dict
    domain: dict

class RasaChatRequest(BaseModel):
    """The payload from our frontend to the /chat proxy."""
    sender: str
    message: str

class KnowledgeQueryRequest(BaseModel):
    """Payload for RAG/LLM queries."""
    query: str
    patient_id: Optional[str] = None

# --- [START] CRITICAL FIX ---
# These models were missing, causing the import error.
class PatientVerifyRequest(BaseModel):
    """Schema for verifying patient login."""
    patient_id: str

class PatientLookupRequest(BaseModel):
    """Schema for looking up Patient ID via email."""
    email: EmailStr
# --- [END] CRITICAL FIX ---