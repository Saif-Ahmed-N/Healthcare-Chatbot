# backend/utils.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import time, date, timedelta
import random
from .models import Doctor, AvailabilitySlot

async def create_initial_data(session: AsyncSession):
    result = await session.execute(select(Doctor))
    if result.scalars().first() is not None:
        print("Database: Doctors exist. Skipping generation.")
        return

    print("Database: Generating Doctors & Slots (Including Sundays)...")
    
    # 1. Doctors List (Same as before)
    doctors_data = [
        ("Dr. Sarah Smith", "Cardiology"), ("Dr. James Wilson", "Cardiology"),
        ("Dr. John Doe", "General Medicine"), ("Dr. Emily Chen", "General Medicine"),
        ("Dr. Lisa Kudrow", "Dermatology"), ("Dr. Shaun Murphy", "Pediatrics"),
        ("Dr. Stephen Strange", "Surgery")
    ] # (Add full list if desired)

    all_doctors = [Doctor(name=n, specialty=s) for n, s in doctors_data]
    session.add_all(all_doctors)
    await session.flush()

    # 2. Slots (7 Days a Week)
    slots = []
    today = date.today()
    
    for doc in all_doctors:
        for i in range(45): # Next 45 days
            d = today + timedelta(days=i)
            # REMOVED the "if Sunday" check. Now we generate for every day.
            
            for h in range(9, 18): # 9 AM - 5 PM
                booked = random.choice([True, False, False, False, False])
                slots.append(AvailabilitySlot(doctor_id=doc.id, date=d, time=time(h,0), is_booked=booked))
    
    session.add_all(slots)
    await session.commit()
    print("Database: Full schedule generated.")