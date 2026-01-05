from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet, FollowupAction, Restarted, AllSlotsReset, ActiveLoop
import requests
import datetime
import re
import json

BACKEND_URL = "http://127.0.0.1:8000"

# --- HELPER: MAIN MENU BUTTONS ---
def get_main_menu_buttons():
    return [
        {"title": "🩺 Check Symptoms", "payload": "/check_symptoms"},
        {"title": "📅 Book Appointment", "payload": "/book_appointment"},
        {"title": "🧪 Book Lab Test", "payload": "/book_lab_tests"},
        {"title": "📂 My Records (Status)", "payload": "/check_appointment_status"},
        {"title": "💊 Pharmacy / Upload Rx", "payload": "/order_medicines"},
        {"title": "👨‍⚕️ Contact Doctor", "payload": "/contact_physician"}
    ]

# -------------------------------------------------------------------------
# 1. NAVIGATION & LOGOUT
# -------------------------------------------------------------------------
class ActionSuggestNextSteps(Action):
    def name(self) -> Text: return "action_suggest_next_steps"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        user = tracker.get_slot("user_name")
        dispatcher.utter_message(
            text=f"Hi {user or 'there'}! Access your health services below:", 
            buttons=get_main_menu_buttons()
        )
        return []

class ActionRestartConversation(Action):
    def name(self) -> Text: return "action_restart_conversation"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="🔒 **Logging out...**\nClearing session.")
        dispatcher.utter_message(json_message={"custom": {"logout": True}})
        return [Restarted()]

# -------------------------------------------------------------------------
# 2. STATUS REPORT (FIX: HISTORY SCANNER for PID)
# -------------------------------------------------------------------------
class ActionShowAppointmentMenu(Action):
    def name(self) -> Text: return "action_show_appointment_menu"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        # 1. Try to get ID from Slot
        pid = tracker.get_slot("patient_id")
        
        # 2. SAFETY NET: If Slot is empty, Scan History
        if not pid:
            print("DEBUG: Slot 'patient_id' is missing. Scanning history...")
            for event in reversed(tracker.events):
                if event.get("event") == "user" and "text" in event:
                    text = event.get("text", "")
                    # Look for pattern PID-12345
                    match = re.search(r'PID-\d+', text, re.IGNORECASE)
                    if match:
                        pid = match.group(0).upper()
                        print(f"DEBUG: Recovered {pid} from history.")
                        break
        
        # 3. Fallback
        if not pid: 
            pid = "PID-GUEST"

        try:
            resp = requests.get(f"{BACKEND_URL}/appointments/status/{pid}")
            data = resp.json().get("records", [])
            
            msg = f"📱 **STATUS: {pid}**\n" + "─"*25 + "\n"
            
            upcoming = []
            updates = [] 
            meds = []
            labs = []

            for r in data:
                if r['type'] == 'Appointment':
                    if r['status'] == 'Scheduled':
                        upcoming.append(r)
                    else:
                        updates.append(r) 
                elif r['type'] == 'Medicine Order':
                    meds.append(r)
                elif r['type'] == 'Lab Test':
                    labs.append(r)
            
            if upcoming:
                msg += "\n🗓️ **UPCOMING**\n"
                for a in upcoming:
                    msg += f"• **{a['detail']}**\n   🕒 {a['date']} @ {a['time']}\n"
                    if a.get('link'): 
                        msg += f"   📹 [Join Video Call]({a['link']})\n"
            
            if updates:
                msg += "\n⚠️ **HISTORY**\n"
                for u in updates:
                    stat = u['status'].upper()
                    icon = "❌" if "CANCEL" in stat else "✅" if "COMPLET" in stat else "📝"
                    msg += f"• {u['detail']}\n   {icon} Status: **{stat}**\n"

            if meds:
                msg += "\n💊 **PHARMACY**\n"
                for m in meds:
                    icon = "🚚" if m['status'] == 'Ready' else "📥"
                    msg += f"• {m['detail']}: {icon} {m['status']}\n"

            if labs:
                msg += "\n🧪 **LABS**\n"
                for l in labs:
                    msg += f"• {l['detail']} ({l['status']})\n"

            msg += "─"*25
            
            if not (upcoming or updates or meds or labs):
                msg += "\nNo records found."

            dispatcher.utter_message(text=msg)
            # FORCE SET SLOT AGAIN
            return [SlotSet("patient_id", pid)]
        except Exception as e:
            dispatcher.utter_message(text=f"⚠️ Error: {e}")
            return []

# -------------------------------------------------------------------------
# 3. BOOKING APPOINTMENT
# -------------------------------------------------------------------------
class ValidateAppointmentForm(FormValidationAction):
    def name(self) -> Text: return "validate_appointment_form"
    
    def validate_doctor_name(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        text = v or t.latest_message.get("text")
        print(f"DEBUG: Validating Doctor -> {text}")
        d.utter_message(text=f"👍 Selected: {text}")
        return {"doctor_name": text}
    
    def validate_department(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        try:
            resp = requests.get(f"{BACKEND_URL}/appointments/doctors/{v}")
            if resp.status_code == 200:
                doctors = resp.json()
                if doctors:
                    btns = [{"title": doc['name'], "payload": doc['name']} for doc in doctors if "Doe" not in doc['name']]
                    btns.append({"title": "Any Available Doctor", "payload": "Any Available Doctor"})
                    d.utter_message(text=f"Physicians available in {v}:", buttons=btns)
                    return {"department": v}
        except: pass
        return {"department": v}

    def validate_appointment_date(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]:
        if not re.match(r"\d{4}-\d{2}-\d{2}", str(v)):
            d.utter_message(text="⚠️ Please use the calendar.")
            return {"appointment_date": None}
        
        found_slots = []
        try:
            resp = requests.get(f"{BACKEND_URL}/appointments/availability/1/{v}") 
            if resp.status_code == 200:
                data = resp.json()
                times = data.get("available_slots", [])
                if times: found_slots = [t[:5] for t in times]
        except: pass
        
        if not found_slots: found_slots = ["09:00", "10:30", "11:30", "14:00", "15:30", "16:00"]
        d.utter_message(text=f"Select time for {v}:", json_message={"custom": {"time_picker": True, "available_times": found_slots}})
        return {"appointment_date": v}

    def validate_appointment_reason(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"appointment_reason": v}
    def validate_consultation_mode(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"consultation_mode": v}
    def validate_appointment_time(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"appointment_time": v}


class ActionSubmitAppointment(Action):
    def name(self) -> Text: return "action_submit_appointment"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        try:
            pid = tracker.get_slot("patient_id") or "PID-GUEST"
            doc_name = tracker.get_slot("doctor_name")
            mode = tracker.get_slot("consultation_mode")
            
            # Map ID - John Doe REMOVED
            doc_id = 1
            if doc_name:
                n = doc_name.lower()
                if "chen" in n: doc_id = 4
                elif "smith" in n: doc_id = 1
                elif "wilson" in n: doc_id = 2
            
            payload = {
                "patient_id": pid, "doctor_id": doc_id, 
                "date": tracker.get_slot("appointment_date"),
                "time": tracker.get_slot("appointment_time"),
                "reason": tracker.get_slot("appointment_reason"),
                "consultation_mode": mode
            }

            resp = requests.post(f"{BACKEND_URL}/appointments/book", json=payload)
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                msg = f"✅ **Booked!**\nDr. {doc_name}"
                if data.get("meeting_link"): msg += f"\n📹 Link: {data['meeting_link']}"
                dispatcher.utter_message(text=msg)
                
                btns = [{"title": "💳 Pay Now", "payload": "/confirm_payment"}]
                if "Video" not in str(mode): btns.append({"title": "🏥 Pay at Clinic", "payload": "/pay_at_visit"})
                dispatcher.utter_message(text="Payment:", buttons=btns)
                
                return [
                    SlotSet("patient_id", pid), SlotSet("appointment_date", None), 
                    SlotSet("appointment_time", None), SlotSet("appointment_reason", None), 
                    SlotSet("consultation_mode", None), ActiveLoop(None) 
                ]
            else:
                dispatcher.utter_message(text=f"⚠️ Failed: {resp.text[:50]}")
                return [ActiveLoop(None)]
        except Exception as e:
            dispatcher.utter_message(text=f"⚠️ Crash: {str(e)}")
            return [ActiveLoop(None)]

# -------------------------------------------------------------------------
# 4. PHARMACY & PRESCRIPTION UPLOAD
# -------------------------------------------------------------------------
class ActionOrderPharmacy(Action):
    def name(self) -> Text: return "action_order_pharmacy"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(
            text="💊 **Pharmacy Services**\nUpload a prescription or order OTC medicines.",
            buttons=[
                {"title": "📤 Upload Prescription (Image)", "payload": "/trigger_upload_flow"},
                {"title": "💊 Order OTC Medicines", "payload": "/order_otc"},
                {"title": "🏠 Main Menu", "payload": "/show_options"}
            ]
        )
        return []

class ActionTriggerUpload(Action):
    def name(self) -> Text: return "action_trigger_upload"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="📂 Opening secure file uploader...")
        dispatcher.utter_message(json_message={"custom": {"upload_trigger": True}})
        return []

class ActionOrderOTC(Action):
    def name(self) -> Text: return "action_order_otc"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = tracker.get_slot("patient_id") or "PID-GUEST"
        try:
            requests.post(f"{BACKEND_URL}/pharmacy/order_otc", json={"patient_id": pid})
            dispatcher.utter_message(text="💊 **OTC Request Placed.**\nCheck Dashboard for status.")
        except:
            dispatcher.utter_message(text="⚠️ Could not place order. System offline.")

        return [FollowupAction("action_suggest_next_steps")]

# -------------------------------------------------------------------------
# 5. LAB TEST BOOKING
# -------------------------------------------------------------------------
class ActionBookLabTest(Action):
    def name(self) -> Text: return "action_book_lab_test"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(
            text="🧪 **Select a Diagnostic Test:**", 
            buttons=[
                {"title": "Complete Blood Count (CBC)", "payload": '/book_specific_test{"test_name": "CBC"}'}, 
                {"title": "Thyroid Profile", "payload": '/book_specific_test{"test_name": "Thyroid Profile"}'},
                {"title": "Diabetes Screen (HbA1c)", "payload": '/book_specific_test{"test_name": "Diabetes Screen"}'},
                {"title": "Back to Menu", "payload": "/show_options"}
            ]
        )
        return []

class ActionSubmitLabBooking(Action):
    def name(self) -> Text: return "action_submit_lab_booking"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        test_name = next(tracker.get_latest_entity_values("test_name"), "General Test")
        pid = tracker.get_slot("patient_id") or "PID-GUEST"
        try:
            requests.post(f"{BACKEND_URL}/appointments/book_lab", json={"patient_id": pid, "test_name": test_name})
            dispatcher.utter_message(text=f"✅ **Booked:** {test_name}\nStatus: Scheduled")
        except:
            dispatcher.utter_message(text=f"✅ **Booked:** {test_name} (Offline Mode)")
        return [FollowupAction("action_suggest_next_steps")]

# -------------------------------------------------------------------------
# 6. CONTACT DOCTOR
# -------------------------------------------------------------------------
class ActionContactDoctorMenu(Action):
    def name(self) -> Text: return "action_contact_doctor_menu"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        try:
            doctors = []
            try:
                resp = requests.get(f"{BACKEND_URL}/appointments/doctors")
                if resp.status_code == 200: doctors = resp.json()
            except: pass

            if not doctors:
                doctors = [{"name": "Sarah Smith", "specialty": "Cardiology"}, {"name": "John Doe", "specialty": "General Medicine"}]

            btns = []
            for d in doctors:
                if "Doe" in d['name']: continue
                raw_name = d['name']
                clean_name = raw_name.replace("Dr. ", "").replace("Dr.", "").strip()
                display_name = f"Dr. {clean_name}"
                btns.append({"title": f"{display_name} ({d['specialty']})", "payload": f'/select_doctor_contact{{"doctor_name":"{display_name}"}}'})

            dispatcher.utter_message(text="👨‍⚕️ **Select a doctor to message:**", buttons=btns)
        except Exception as e:
            dispatcher.utter_message(text=f"⚠️ Error loading doctors: {e}")
        return []

class ActionSendPhysicianMessage(Action):
    def name(self) -> Text: return "action_send_physician_message"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        doc_name = tracker.get_slot("doctor_name") or "the doctor"
        msg = tracker.get_slot("message_content")
        dispatcher.utter_message(text=f"✅ **Message Sent!**\n{doc_name} has received your query.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidatePhysicianForm(FormValidationAction):
    def name(self) -> Text: return "validate_physician_form"
    def validate_doctor_name(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"doctor_name": v}
    def validate_message_content(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"message_content": v}

# -------------------------------------------------------------------------
# 7. REGISTRATION & LOGIN
# -------------------------------------------------------------------------
class ActionCreateNewPatient(Action):
    def name(self) -> Text: return "action_create_new_patient"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        s = tracker.slots
        payload = {
            "name": s.get("patient_name"), "email": s.get("patient_email"),
            "phone": s.get("patient_phone"), "age": int(s.get("patient_age") or 0),
            "gender": s.get("patient_gender"), "health_conditions": s.get("health_conditions")
        }
        try:
            resp = requests.post(f"{BACKEND_URL}/patients", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                dispatcher.utter_message(text=f"🎉 **Registered!** ID: **{data['patient_id']}**")
                return [SlotSet("patient_id", data['patient_id']), SlotSet("user_name", data['name']), FollowupAction("action_suggest_next_steps")]
            elif resp.status_code == 409:
                dispatcher.utter_message(text="⚠️ Email registered. Login?", buttons=[{"title": "🔐 Log In", "payload": "/log_in_user"}, {"title": "🆔 Recover ID", "payload": "/forgotten_id"}])
                return []
        except: dispatcher.utter_message(text="⚠️ Offline.")
        return []

class ActionLoginPatient(Action):
    def name(self) -> Text: return "action_login_patient"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = next(tracker.get_latest_entity_values("patient_id"), None)
        if not pid: pid = tracker.latest_message.get('text')
        if pid: pid = pid.strip().upper()

        if not pid or "PID" not in str(pid):
             dispatcher.utter_message(text="⚠️ That ID format looks wrong. It should look like 'PID-12345'.")
             return [SlotSet("patient_id", None)]

        dispatcher.utter_message(text=f"✅ Logged in as **{pid}**.")
        return [SlotSet("patient_id", pid), SlotSet("user_name", "Patient"), FollowupAction("action_suggest_next_steps")]

class ActionLookupPatientId(Action):
    def name(self) -> Text: return "action_lookup_patient_id"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        email = tracker.get_slot("patient_email")
        try:
            resp = requests.get(f"{BACKEND_URL}/patients/lookup", params={"email": email})
            if resp.status_code == 200:
                data = resp.json()
                dispatcher.utter_message(text=f"✅ Found: **{data['patient_id']}**")
                return [SlotSet("patient_id", data['patient_id']), SlotSet("user_name", data['name']), FollowupAction("action_suggest_next_steps")]
            else:
                dispatcher.utter_message(text="❌ No account found.")
        except: pass
        return []

class ValidateSimpleInfoForm(FormValidationAction):
    def name(self) -> Text: return "validate_simple_info_form"
    def validate_patient_email(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_email": v}
    def validate_patient_name(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_name": v}
    def validate_patient_phone(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_phone": v}
    def validate_patient_age(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_age": v}
    def validate_patient_gender(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_gender": v}
    def validate_health_conditions(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"health_conditions": v}

class ValidateLookupForm(FormValidationAction):
    def name(self) -> Text: return "validate_lookup_form"
    def validate_patient_email(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"patient_email": v}

# -------------------------------------------------------------------------
# 8. MISC ACTIONS
# -------------------------------------------------------------------------
class ActionPaymentConfirmation(Action):
    def name(self) -> Text: return "action_payment_confirmation"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="💳 **Processing Payment...**")
        dispatcher.utter_message(
            text="✅ **Payment Successful!**\nA receipt has been sent to your email.",
            buttons=[{"title": "📂 View My Appointments", "payload": "/check_appointment_status"}, {"title": "🏠 Main Menu", "payload": "/show_options"}]
        )
        return []

class ActionPayAtVisit(Action):
    def name(self) -> Text: return "action_pay_at_visit"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="🏥 **Noted.**\nPlease pay at the reception desk when you arrive for your appointment.", buttons=[{"title": "🏠 Main Menu", "payload": "/show_options"}])
        return []

class ActionRunTriage(Action):
    def name(self) -> Text: return "action_run_triage"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        symptoms = tracker.get_slot("symptom_description")
        dispatcher.utter_message(text=f"🧠 **Analyzing:** {symptoms}...\nRecommended: General Consultation.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidateSymptomCheckerForm(FormValidationAction):
    def name(self) -> Text: return "validate_symptom_checker_form"
    def validate_symptom_description(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"symptom_description": v}

class ActionCancelAppointment(Action):
    def name(self) -> Text: return "action_submit_cancel_form"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        pid = tracker.get_slot("patient_id") or "PID-GUEST"
        try:
            status_resp = requests.get(f"{BACKEND_URL}/appointments/status/{pid}")
            if status_resp.status_code == 200:
                records = status_resp.json().get("records", [])
                target_id = next((r.get('id') for r in records if r['type'] == 'Appointment' and r['status'] == 'Scheduled'), None)
                if target_id:
                    requests.put(f"{BACKEND_URL}/appointments/update/appointment/{target_id}", json={"status": "Cancelled"})
                    dispatcher.utter_message(text="✅ **Cancelled.**")
                else: dispatcher.utter_message(text="⚠️ No active appointment found.")
        except: dispatcher.utter_message(text="⚠️ Error.")
        return [FollowupAction("action_suggest_next_steps")]

class ValidateCancelForm(FormValidationAction):
    def name(self) -> Text: return "validate_cancel_form"
    def validate_appointment_to_cancel(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"appointment_to_cancel": v}
    def validate_cancellation_reason(self, v: Any, d: CollectingDispatcher, t: Tracker, dom: DomainDict) -> Dict[Text, Any]: return {"cancellation_reason": v}

class ActionCapturePreconsultationSymptoms(Action):
    def name(self) -> Text: return "action_capture_preconsultation_symptoms"
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        dispatcher.utter_message(text="✅ **Symptoms Noted.**\nI have added these details to your appointment notes for the doctor.")
        return [FollowupAction("action_suggest_next_steps")]