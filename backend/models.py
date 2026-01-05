# backend/models.py
from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, Time, DateTime, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

# --- 1. PATIENTS ---
class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    age = Column(Integer)
    gender = Column(String)
    health_conditions = Column(String, nullable=True)
    
    appointments = relationship("Appointment", back_populates="patient")
    lab_requests = relationship("LabRequest", back_populates="patient")
    prescriptions = relationship("Prescription", back_populates="patient")

# --- 2. DOCTORS ---
class Doctor(Base):
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    specialty = Column(String) # "Cardiology"
    
    availability = relationship("AvailabilitySlot", back_populates="doctor")
    appointments = relationship("Appointment", back_populates="doctor")

# --- 3. AVAILABILITY SLOTS ---
class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    date = Column(Date)
    time = Column(Time)
    is_booked = Column(Boolean, default=False)
    
    doctor = relationship("Doctor", back_populates="availability")
    appointment = relationship("Appointment", back_populates="slot", uselist=False)

class Appointment(Base):
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    slot_id = Column(Integer, ForeignKey("availability_slots.id"))
    
    reason = Column(String)
    consultation_mode = Column(String) # "In-Person" or "Video Call"
    meeting_link = Column(String, nullable=True) # <--- NEW COLUMN FOR ZOOM LINK
    status = Column(String, default="Scheduled")
    
    patient = relationship("Patient", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    slot = relationship("AvailabilitySlot", back_populates="appointment")
# --- 5. LAB REQUESTS (New) ---
class LabRequest(Base):
    __tablename__ = "lab_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    test_name = Column(String)
    status = Column(String, default="Scheduled") # Scheduled, In Progress, Completed
    date_requested = Column(Date, default=datetime.now().date)
    
    patient = relationship("Patient", back_populates="lab_requests")

class Prescription(Base):
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    image_filename = Column(String) # Store filename, not full path
    status = Column(String, default="Processing") # Processing, Ready for Pickup
    pharmacist_note = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    patient = relationship("Patient", back_populates="prescriptions")