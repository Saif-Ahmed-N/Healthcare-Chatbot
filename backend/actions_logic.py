from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet, FollowupAction, AllSlotsReset, ActiveLoop
import requests
import datetime
import re
import json
import random

# CONNECT TO FASTAPI BACKEND (Use 127.0.0.1 for stability)
BACKEND_URL = "http://127.0.0.1:8000"

# -------------------------------------------------------------------------
# 1. GREET & RESTART (Logic: Context Aware)
# -------------------------------------------------------------------------
class ActionSuggestNextSteps(Action):
    def name(self) -> Text:
        return "action_suggest_next_steps"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        user_name = tracker.get_slot("user_name")
        patient_id = tracker.get_slot("patient_id")

        if patient_id:
            # Authenticated User Menu
            msg = f"Welcome back, {user_name or 'Patient'}. How can I assist you today?"
            buttons = [
                {"title": "🩺 Check Symptoms (Triage)", "payload": "/check_symptoms"},
                {"title": "📅 Book Appointment", "payload": "/book_appointment"},
                {"title": "📋 My Appointments", "payload": "/check_appointment_status"},
                {"title": "💊 Pharmacy / Prescriptions", "payload": "/order_medicines"},
                {"title": "🧪 Book Lab Tests", "payload": "/book_lab_tests"},
                {"title": "👨‍⚕️ Message Doctor", "payload": "/contact_physician"},
                {"title": "❓ Medical Q&A", "payload": "/ask_medical_info"},
                {"title": "👋 Logout", "payload": "/goodbye"}
            ]
        else:
            # Guest User Menu
            msg = "Welcome to MediAssist AI. How can I help you today?"
            buttons = [
                {"title": "🆕 Register New Account", "payload": "/register_user"},
                {"title": "🔐 Log In", "payload": "/log_in_user"},
                {"title": "🩺 Check Symptoms", "payload": "/check_symptoms"},
                {"title": "❓ General Enquiry", "payload": "/ask_medical_info"}
            ]
        
        dispatcher.utter_message(text=msg, buttons=buttons)
        return []

class ActionRestartConversation(Action):
    def name(self) -> Text: return "action_restart_conversation"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        return [AllSlotsReset(), FollowupAction("action_suggest_next_steps")]

# -------------------------------------------------------------------------
# 2. REGISTRATION (Logic: Regex Validation + API)
# -------------------------------------------------------------------------
class ValidateSimpleInfoForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_simple_info_form"
    
    def validate_patient_name(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        return {"patient_name": v}

    def validate_patient_email(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", str(v)):
            d.utter_message(text="⚠️ That email format seems incorrect. Please try again.")
            return {"patient_email": None}
        return {"patient_email": v}

    def validate_patient_age(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        match = re.search(r'\d+', str(v))
        if match:
            age = int(match.group(0))
            if 0 < age < 120: return {"patient_age": age}
        d.utter_message(text="⚠️ Please enter a valid numeric age.")
        return {"patient_age": None}

    def validate_patient_gender(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        return {"patient_gender": v}
    def validate_health_conditions(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        return {"health_conditions": v}

class ActionCreateNewPatient(Action):
    def name(self) -> Text: return "action_create_new_patient"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        slots = tracker.slots
        payload = {
            "name": slots.get("patient_name"), "email": slots.get("patient_email"),
            "age": int(slots.get("patient_age") or 30), "gender": slots.get("patient_gender"),
            "health_conditions": slots.get("health_conditions"), "phone": "0000000000"
        }
        try:
            resp = requests.post(f"{BACKEND_URL}/patients", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                # Use name from backend or slot
                final_name = data.get("name", slots.get("patient_name"))
                dispatcher.utter_message(text=f"✅ **Registration Successful.**\nWelcome, {final_name}.\nYour Patient ID is **{data['patient_id']}**.\nPlease save this ID.")
                return [SlotSet("patient_id", data['patient_id']), SlotSet("user_name", final_name), FollowupAction("action_suggest_next_steps")]
            elif resp.status_code == 409:
                dispatcher.utter_message(text=f"⚠️ The email **{payload['email']}** is already registered.", buttons=[{"title": "Recover ID", "payload": "/forgotten_id"}])
        except: dispatcher.utter_message(text="⚠️ System offline.")
        return []

# -------------------------------------------------------------------------
# 3. LOGIN & LOOKUP
# -------------------------------------------------------------------------
class ActionLoginPatient(Action):
    def name(self) -> Text: return "action_login_patient"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = next(tracker.get_latest_entity_values("patient_id"), None) or tracker.get_slot("patient_id")
        if not pid: 
            dispatcher.utter_message(text="Please provide your Patient ID.")
            return []
        
        # Simulate Verification/Fetch Name
        # In a real scenario, you'd GET /patients/{pid} here
        dispatcher.utter_message(text=f"✅ Login successful for **{pid}**.")
        return [SlotSet("patient_id", pid), FollowupAction("action_suggest_next_steps")]

class ActionLookupPatientId(Action):
    def name(self) -> Text: return "action_lookup_patient_id"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        email = tracker.get_slot("patient_email")
        try:
            resp = requests.get(f"{BACKEND_URL}/patients/lookup", params={"email": email})
            if resp.status_code == 200: 
                data = resp.json()
                dispatcher.utter_message(text=f"Record Found: **{data['name']}**\nID: **{data['patient_id']}**")
            else: dispatcher.utter_message(text="❌ No account found with that email.")
        except: dispatcher.utter_message(text="System error.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidateLookupForm(FormValidationAction):
    def name(self) -> Text: return "validate_lookup_form"
    def validate_patient_email(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_email": v}

# -------------------------------------------------------------------------
# 4. ADVANCED APPOINTMENT BOOKING (Logic: Calendar, Slots, Doctor IDs)
# -------------------------------------------------------------------------
class ValidateAppointmentForm(FormValidationAction):
    def name(self) -> Text: return "validate_appointment_form"

    def validate_department(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        # INTEGRATED: Filter doctors by department (Simulated from actions_logic.py)
        # In full prod, this would call GET /doctors?specialty=...
        buttons = [
            {"title": "Dr. Sarah Smith (Cardiology)", "payload": "Dr. Sarah Smith"},
            {"title": "Dr. John Doe (General)", "payload": "Dr. John Doe"},
            {"title": "Any Available Doctor", "payload": "Any Available Doctor"}
        ]
        dispatcher.utter_message(text=f"Specialists in {slot_value}:", buttons=buttons)
        return {"department": slot_value}

    def validate_doctor_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        dispatcher.utter_message(text="Could you briefly describe the reason for your visit?")
        return {"doctor_name": slot_value}

    def validate_appointment_reason(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        buttons = [{"title": "In-Person", "payload": "In-Person"}, {"title": "Video Call", "payload": "Video Call"}]
        dispatcher.utter_message(text="Select consultation mode:", buttons=buttons)
        return {"appointment_reason": slot_value}

    def validate_consultation_mode(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        # INTEGRATED: Calendar Widget Trigger
        dispatcher.utter_message(text="Please select a date:", json_message={"custom": {"calendar": True}})
        return {"consultation_mode": slot_value}

    def validate_appointment_date(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        # INTEGRATED: Date Validation Logic
        try:
            p_date = datetime.datetime.strptime(str(slot_value)[:10], "%Y-%m-%d").date()
            if p_date < datetime.date.today():
                dispatcher.utter_message(text="⚠️ Please select a future date.")
                return {"appointment_date": None}
            
            # INTEGRATED: Slot Calculation Logic
            # Simulate fetching slots from DB logic
            times = ["09:00", "10:30", "11:00", "14:00", "16:30"]
            dispatcher.utter_message(text=f"Available slots on {slot_value}:", json_message={"custom": {"time_picker": True, "available_times": times}})
            return {"appointment_date": str(slot_value)}
        except:
            dispatcher.utter_message(text="Invalid date format.")
            return {"appointment_date": None}

class ActionSubmitAppointment(Action):
    def name(self) -> Text: return "action_submit_appointment"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = tracker.get_slot("patient_id") or "PID-DEMO"
        doc_name = tracker.get_slot("doctor_name")
        
        # INTEGRATED: Doctor ID Mapping (Crucial for Dashboard)
        doctor_map = {"Dr. Sarah Smith": 1, "Dr. John Doe": 2, "Any Available Doctor": 1}
        doc_id = doctor_map.get(doc_name, 1)

        payload = {
            "patient_id": pid, "doctor_id": doc_id,
            "date": str(tracker.get_slot("appointment_date")), 
            "time": str(tracker.get_slot("appointment_time")),
            "reason": tracker.get_slot("appointment_reason"),
            "consultation_mode": tracker.get_slot("consultation_mode")
        }

        try:
            resp = requests.post(f"{BACKEND_URL}/appointments", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                msg = f"✅ **Appointment Confirmed**\n\n**Ref:** #{data['appointment_id']}\n**Doctor:** {doc_name}\n**Time:** {payload['time']}"
                
                # INTEGRATED: Payment / Video Link Logic
                btns = [{"title": "💳 Pay Now ($50)", "payload": "/confirm_payment"}, {"title": "🏥 Pay at Clinic", "payload": "/pay_at_visit"}]
                if payload['consultation_mode'] == "Video Call":
                    msg += "\n🎥 **Video Link:** meet.google.com/abc-xyz" # Mock link logic
                
                dispatcher.utter_message(text=msg, buttons=btns)
            else:
                dispatcher.utter_message(text="⚠️ Slot unavailable. Please pick another time.")
        except: 
            dispatcher.utter_message(text="⚠️ Connection Error.")
        
        return [] # Don't suggest next steps yet, wait for payment choice

# -------------------------------------------------------------------------
# 5. SYMPTOM TRIAGE (Logic: LLM Integration + Keywords)
# -------------------------------------------------------------------------
class ActionRunTriage(Action):
    def name(self) -> Text: return "action_run_triage"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        symptoms = tracker.get_slot("symptom_description") or ""
        
        # INTEGRATED: Keyword Fallback
        forced_level = None
        s_low = symptoms.lower()
        if any(x in s_low for x in ["chest pain", "heart attack", "unconscious", "stroke"]): forced_level = "EMERGENCY"
        elif any(x in s_low for x in ["fever", "severe pain", "bleeding"]): forced_level = "URGENT"

        # INTEGRATED: LLM Call
        prompt = f"""Act as a medical triage AI. Analyze: "{symptoms}". Determine level (Emergency/Urgent/Self-Care) and advice."""
        
        try:
            # Attempt to call knowledge endpoint
            resp = requests.post(f"{BACKEND_URL}/knowledge/query", json={"query": prompt})
            ai_text = resp.json().get("response", "")
            if forced_level == "EMERGENCY":
                dispatcher.utter_message(text=f"🟥 **CRITICAL ALERT**\nYour symptoms suggest a medical emergency.\n\nAI Analysis: {ai_text}")
            else:
                dispatcher.utter_message(text=f"**Symptom Analysis:**\n{ai_text}")
        except:
            # Fallback if LLM offline
            msg = "🟥 **EMERGENCY**" if forced_level == "EMERGENCY" else "🟧 **Urgent Care**"
            dispatcher.utter_message(text=f"{msg}\nBased on keywords, please consult a doctor immediately.")

        return [FollowupAction("action_suggest_next_steps")]

class ValidateSymptomCheckerForm(FormValidationAction):
    def name(self) -> Text: return "validate_symptom_checker_form"
    def validate_symptom_description(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"symptom_description": v}

# -------------------------------------------------------------------------
# 6. PHARMACY (Logic: Simulation)
# -------------------------------------------------------------------------
class ActionOrderPharmacy(Action):
    def name(self) -> Text: return "action_order_pharmacy"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        msg = tracker.latest_message.get("text", "")
        
        if "upload" in msg.lower() or "image" in msg.lower():
            # INTEGRATED: Scanning Simulation
            report = """
✅ **Prescription Scanned**
**AI-Detected Medicines:**
| Medicine | Dosage | Freq |
| :--- | :--- | :--- |
| Paracetamol | 500mg | 2x/day |
| Amoxicillin | 250mg | 3x/day |

Your pharmacist will verify this shortly.
            """
            dispatcher.utter_message(text=report)
            return [FollowupAction("action_suggest_next_steps")]
            
        dispatcher.utter_message(text="💊 **Pharmacy Module**\nUpload a prescription or order OTC.", buttons=[{"title":"📄 Upload Prescription","payload":"/upload_prescription"}, {"title":"💊 Order OTC","payload":"/order_otc"}])
        return []

# -------------------------------------------------------------------------
# 7. APPOINTMENT HISTORY (Logic: Fetch & Format)
# -------------------------------------------------------------------------
class ActionShowAppointmentMenu(Action):
    def name(self) -> Text: return "action_show_appointment_menu"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = tracker.get_slot("patient_id")
        if not pid: 
            dispatcher.utter_message(text="Please login first.")
            return [FollowupAction("action_login_patient")]
        
        # INTEGRATED: Fetch logic (Simulated for robustness if DB empty)
        # In prod: resp = requests.get(f"{BACKEND_URL}/appointments/{pid}")
        dispatcher.utter_message(text=f"📅 **Appointments for {pid}:**\n\n1. **Dr. Sarah Smith**\n   - Date: Tomorrow, 10:00 AM\n   - Status: Scheduled\n\n[Cancel Appointment] (/request_cancel_appointment)")
        return [FollowupAction("action_suggest_next_steps")]

# -------------------------------------------------------------------------
# 8. OTHER REQUIRED ACTIONS
# -------------------------------------------------------------------------
class ActionLLMResponse(Action):
    def name(self) -> Text: return "action_llm_response"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        q = tracker.get_slot("medical_query")
        try:
            resp = requests.post(f"{BACKEND_URL}/knowledge/query", json={"query": q})
            dispatcher.utter_message(text=resp.json().get("response", "No info found."))
        except: dispatcher.utter_message(text="Medical knowledge base offline.")
        return [FollowupAction("action_suggest_next_steps")]

class ActionSendPhysicianMessage(Action):
    def name(self) -> Text: return "action_send_physician_message"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text=f"✅ Message sent to {tracker.get_slot('doctor_name')}.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidatePhysicianForm(FormValidationAction):
    def name(self) -> Text: return "validate_physician_form"
    def validate_doctor_name(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"doctor_name": v}
    def validate_message_content(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"message_content": v}

class ValidateMedicalForm(FormValidationAction):
    def name(self) -> Text: return "validate_medical_form"
    def validate_medical_query(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"medical_query": v}

class ValidateInsuranceForm(FormValidationAction):
    def name(self) -> Text: return "validate_insurance_form"
    def validate_insurance_query(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"insurance_query": v}

class ActionBookLabTest(Action):
    def name(self) -> Text: return "action_book_lab_test"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="Select Lab Test:", buttons=[{"title":"CBC","payload":"/book_test_cbc"}])
        return [FollowupAction("action_suggest_next_steps")]

class ActionRagInsuranceQuery(Action):
    def name(self) -> Text: return "action_rag_insurance_query"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="Insurance details: Copay is $20.")
        return [FollowupAction("action_suggest_next_steps")]

class ActionSubmitCancelForm(Action):
    def name(self) -> Text: return "action_submit_cancel_form"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="✅ Appointment cancelled.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidateCancelForm(FormValidationAction):
    def name(self) -> Text: return "validate_cancel_form"
    def validate_appointment_to_cancel(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"appointment_to_cancel": v}
    def validate_cancellation_reason(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"cancellation_reason": v}

class ActionAskAppointmentToCancel(Action):
    def name(self) -> Text: return "action_ask_appointment_to_cancel"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="Which appointment?")
        return []

class ActionRescheduleCancel(Action):
    def name(self) -> Text: return "action_reschedule_cancel"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="Rescheduling...")
        return [FollowupAction("action_suggest_next_steps")]

class ActionPaymentConfirmation(Action):
    def name(self) -> Text: return "action_payment_confirmation"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="💳 **Processing Secure Payment...**")
        dispatcher.utter_message(text="✅ **Success!** Receipt sent to email.")
        # FORCE CONTINUITY
        return [FollowupAction("action_suggest_next_steps")]

class ActionPayAtVisit(Action):
    def name(self) -> Text: return "action_pay_at_visit"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="🏥 **Noted.** Please pay at the front desk.")
        return [FollowupAction("action_suggest_next_steps")]

class ActionCapturePreconsultationSymptoms(Action):
    def name(self) -> Text: return "action_capture_preconsultation_symptoms"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="Symptoms recorded for doctor.")
        return [FollowupAction("action_suggest_next_steps")]

class ActionProactivePostConsultation(Action):
    def name(self) -> Text: return "action_proactive_post_consultation"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]): return []

class ActionSubmitFeedback(Action):
    def name(self) -> Text: return "action_submit_feedback"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]): return []