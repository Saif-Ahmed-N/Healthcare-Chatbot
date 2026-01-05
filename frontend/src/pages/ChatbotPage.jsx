import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Flatpickr from 'react-flatpickr';
import "flatpickr/dist/themes/airbnb.css";
import { 
  Send, Paperclip, LayoutDashboard, X, MessageSquare, UploadCloud, 
  ShieldCheck, Activity, Calendar, MoreHorizontal, FileText 
} from 'lucide-react';
import { Link } from 'react-router-dom';

const API_URL = "http://localhost:8000/chat";

// --- PERSIST SESSION ID ---
const getSenderId = () => {
  let id = localStorage.getItem("chat_sender_id");
  if (!id) {
    id = "user_" + Math.random().toString(36).substring(7);
    localStorage.setItem("chat_sender_id", id);
  }
  return id;
};
const SENDER_ID = getSenderId();

const ChatbotPage = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [showPicker, setShowPicker] = useState(false);
  const [pickerType, setPickerType] = useState(null); 
  const [pickerOptions, setPickerOptions] = useState([]);
  const [showUpload, setShowUpload] = useState(false); 
  
  const chatContainerRef = useRef(null);
  const hasGreeted = useRef(false);

  useEffect(() => {
    if (chatContainerRef.current) chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
  }, [messages, isTyping, showPicker, showUpload]);

  useEffect(() => {
    if (!hasGreeted.current && messages.length === 0) { 
        sendMessageToBackend("/greet"); 
        hasGreeted.current = true; 
    }
  }, []);

  const addMessage = (text, sender = "bot") => setMessages(prev => [...prev, { text, sender }]);

  const renderMessageText = (text) => {
      if (!text) return null;
      let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      formatted = formatted.replace(/\n/g, '<br/>');
      return <div dangerouslySetInnerHTML={{ __html: formatted }} />;
  };

  const sendMessageToBackend = async (messageText) => {
    setIsTyping(true); setShowPicker(false);
    try {
      const response = await axios.post(API_URL, { sender: SENDER_ID, message: messageText });
      setIsTyping(false);
      const data = response.data;

      data.forEach(res => {
        if (res.text) {
            addMessage(res.text, "bot");
            if (res.text.includes("Logged in as")) {
                const match = res.text.match(/PID-\d+/);
                if (match) localStorage.setItem("current_patient_id", match[0]);
            }
        }
        if (res.buttons) setMessages(prev => [...prev, { buttons: res.buttons, sender: "bot-buttons" }]);
        
        let custom = res.custom;
        if (!custom && res.json_message) custom = res.json_message.custom || res.json_message;

        if (custom) {
          if (custom.upload_trigger === true || custom.upload_trigger === "true") setShowUpload(true); 
          if (custom.calendar) { setPickerType("calendar"); setShowPicker(true); }
          if (custom.time_picker) { 
             setPickerType("time"); 
             const slots = custom.available_times || generateFallbackSlots();
             setPickerOptions(slots);
             setShowPicker(true); 
          }
          if (custom.logout) {
             localStorage.removeItem("chat_sender_id");
             localStorage.removeItem("current_patient_id");
             window.location.reload(); 
          }
        }
      });
    } catch (error) { setIsTyping(false); }
  };

  const generateFallbackSlots = () => {
    const slots = [];
    const now = new Date();
    const currentHour = now.getHours();
    const isToday = new Date().toISOString().split('T')[0];
    for (let hour = 9; hour < 17; hour++) {
      if (!isToday || hour > currentHour) slots.push(`${hour.toString().padStart(2, '0')}:00`);
      if (!isToday || hour > currentHour) slots.push(`${hour.toString().padStart(2, '0')}:30`);
    }
    return slots.length > 0 ? slots : ["No slots left today"];
  };

  const handleDateSelect = ([date]) => { 
     if (!date) return;
     const offset = date.getTimezoneOffset();
     const d = new Date(date.getTime() - (offset * 60 * 1000)).toISOString().split('T')[0];
     addMessage(d, "user"); sendMessageToBackend(d); 
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    addMessage(`📄 Uploading ${file.name}...`, "user");
    setShowUpload(false);
    
    const pid = localStorage.getItem("current_patient_id") || "PID-GUEST";
    const formData = new FormData();
    formData.append("file", file);
    formData.append("patient_id", pid); 

    try {
        await axios.post("http://localhost:8000/appointments/upload_prescription", formData);
        sendMessageToBackend("/inform_upload_success"); 
    } catch (err) { addMessage("❌ Upload failed.", "bot"); }
  };

  const handleSend = (e) => { e.preventDefault(); if(!input.trim()) return; addMessage(input, "user"); sendMessageToBackend(input); setInput(""); };

  // ================= CLINICAL PRO UI =================
  return (
    <div className="flex justify-center items-center min-h-screen bg-[#e2e8f0] font-sans p-4">
      
      {/* MAIN CONTAINER: Solid, Professional, Shadowed */}
      <div className="w-full max-w-[450px] h-[90vh] bg-white rounded-lg shadow-xl flex flex-col overflow-hidden relative border border-slate-300">
        
        {/* HEADER: Deep Navy for Authority */}
        <header className="h-16 bg-[#0f172a] flex items-center justify-between px-6 shrink-0 z-20 shadow-md">
             <div className="flex items-center gap-3">
                <div className="w-9 h-9 bg-teal-500 rounded flex items-center justify-center text-white shadow-sm">
                    <Activity size={20} strokeWidth={2.5}/>
                </div>
                <div>
                    <h1 className="text-base font-bold text-white tracking-wide">MediAssist<span className="text-teal-400">Pro</span></h1>
                    <span className="text-[10px] font-medium text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
                        <span className="w-1.5 h-1.5 bg-teal-400 rounded-full"></span> 
                        Active Session
                    </span>
                </div>
             </div>
             <div className="flex items-center gap-3">
                <Link to="/dashboard" className="text-slate-300 hover:text-white transition-colors" title="Dashboard">
                    <LayoutDashboard size={20}/>
                </Link>
                <button className="text-slate-300 hover:text-white transition-colors"><MoreHorizontal size={20}/></button>
             </div>
        </header>

        {/* CHAT AREA: Clean White/Gray Contrast */}
        <main ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#f1f5f9]">
          
          <div className="flex justify-center pb-2">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest border-b border-slate-300 pb-1">
                Consultation Started
            </span>
          </div>

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"} animate-in fade-in slide-in-from-bottom-2`}>
              
              {/* Message Bubble */}
              {msg.text && (
                <div className={`max-w-[85%] px-5 py-3.5 text-[15px] leading-relaxed shadow-sm font-medium
                    ${msg.sender === "user" 
                        ? "bg-[#0f172a] text-white rounded-xl rounded-tr-none" 
                        : "bg-white text-slate-800 border border-slate-200 rounded-xl rounded-tl-none"
                    }`}>
                   {renderMessageText(msg.text)}
                </div>
              )}

              {/* Bot Identity Label */}
              {msg.sender === 'bot' && idx === messages.length - 1 && !msg.buttons && (
                  <span className="text-[10px] text-slate-500 mt-1.5 ml-1 font-semibold">AI Assistant</span>
              )}

              {/* Buttons: Clinical Teal */}
              {msg.buttons && (
                <div className="flex flex-wrap gap-2 mt-2">
                    {msg.buttons.map((btn, b) => (
                        <button key={b} onClick={() => { addMessage(btn.title, "user"); sendMessageToBackend(btn.payload); }} 
                            className="px-4 py-2 bg-white border border-teal-100 text-teal-700 rounded-lg text-xs font-bold uppercase tracking-wide hover:bg-teal-50 hover:border-teal-300 transition-all shadow-sm">
                            {btn.title}
                        </button>
                    ))}
                </div>
              )}
            </div>
          ))}
          
          {isTyping && (
            <div className="flex items-center gap-1 ml-1 text-slate-400 bg-white px-3 py-2 rounded-lg border border-slate-200 w-fit">
                <span className="text-xs font-semibold mr-1">Typing</span>
                <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce"></span>
                <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce delay-75"></span>
                <span className="w-1 h-1 bg-slate-400 rounded-full animate-bounce delay-150"></span>
            </div>
          )}
        </main>

        {/* INPUT AREA: Solid Footer */}
        <div className="bg-white border-t border-slate-200 p-5 shrink-0 z-10 relative">
           
           {/* Upload Modal */}
           {showUpload && (
            <div className="absolute bottom-20 left-5 right-5 bg-white p-4 rounded-lg shadow-2xl border border-slate-200 animate-in slide-in-from-bottom-2 z-20">
                <div className="flex justify-between items-center mb-3 border-b border-slate-100 pb-2">
                    <span className="font-bold text-xs text-slate-700 uppercase flex items-center gap-2">
                        <UploadCloud size={16} className="text-teal-600"/> Upload Record
                    </span>
                    <button onClick={() => setShowUpload(false)}><X size={16} className="text-slate-400 hover:text-slate-600"/></button>
                </div>
                <input type="file" onChange={handleFileUpload} className="block w-full text-xs text-slate-500 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:text-xs file:font-bold file:bg-teal-50 file:text-teal-700 hover:file:bg-teal-100 cursor-pointer"/>
            </div>
           )}
           
           {/* Picker Modal */}
           {showPicker && (
            <div className="absolute bottom-20 left-5 right-5 bg-white rounded-lg shadow-2xl border border-slate-200 overflow-hidden animate-in slide-in-from-bottom-2 z-20">
               <div className="flex justify-between p-3 bg-slate-50 border-b border-slate-100">
                   <span className="font-bold text-xs text-slate-600 uppercase flex items-center gap-2"><Calendar size={14}/> Select Option</span>
                   <button onClick={() => setShowPicker(false)}><X size={16} className="text-slate-400 hover:text-slate-600"/></button>
               </div>
               <div className="p-3 flex flex-wrap justify-center gap-2 max-h-48 overflow-y-auto">
                  {pickerType === 'calendar' ? <Flatpickr options={{ inline: true, minDate: "today" }} onChange={handleDateSelect} /> : 
                   pickerOptions.map(t => <button key={t} onClick={() => {addMessage(t, "user"); sendMessageToBackend(t)}} className="px-4 py-2 bg-slate-50 border border-slate-200 rounded text-xs font-semibold text-slate-700 hover:bg-teal-600 hover:text-white hover:border-teal-600 transition-colors">{t}</button>)}
               </div>
            </div>
           )}
           
           {/* Input Bar */}
           <form onSubmit={handleSend} className="flex gap-3 items-center">
            <button type="button" onClick={() => setShowUpload(true)} className="p-2.5 bg-slate-100 rounded-md text-slate-500 hover:bg-slate-200 hover:text-slate-800 transition-colors border border-slate-200">
                <Paperclip size={18} />
            </button>
            
            <div className="flex-1 relative">
                <input 
                    type="text" 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)} 
                    placeholder="Type your health concern..." 
                    className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm rounded-md px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:bg-white transition-all placeholder:text-slate-400 font-medium"
                />
            </div>
            
            <button type="submit" disabled={!input.trim()} 
                className={`p-2.5 rounded-md text-white shadow-sm transition-all duration-200 
                ${input.trim() ? "bg-teal-600 hover:bg-teal-700" : "bg-slate-300 cursor-not-allowed"}`}>
                <Send size={18} />
            </button>
          </form>
          
          <div className="text-center mt-3">
             <span className="text-[10px] font-semibold text-slate-400 flex items-center justify-center gap-1.5">
                <ShieldCheck size={12} className="text-teal-500"/> HIPAA COMPLIANT & ENCRYPTED
             </span>
          </div>
        </div>

      </div>
    </div>
  );
};

export default ChatbotPage;