import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Flatpickr from 'react-flatpickr';
import "flatpickr/dist/themes/airbnb.css";
import { Send, Paperclip, LayoutDashboard, X, MessageSquare, UploadCloud, ShieldCheck, Activity, Calendar } from 'lucide-react';
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
  const [selectedDate, setSelectedDate] = useState(null); 
  const [showUpload, setShowUpload] = useState(false); 
  
  const chatContainerRef = useRef(null);
  const hasGreeted = useRef(false);

  // --- AUTO SCROLL ---
  useEffect(() => {
    if (chatContainerRef.current) chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
  }, [messages, isTyping, showPicker, showUpload]);

  // --- INITIAL GREETING ---
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

  // --- BACKEND LOGIC ---
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
    const isToday = selectedDate === now.toISOString().split('T')[0];
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
     setSelectedDate(d); addMessage(d, "user"); sendMessageToBackend(d); 
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

  // ================= PROFESSIONAL UI RENDER =================
  return (
    <div className="flex justify-center items-center min-h-screen bg-[#F1F5F9] font-sans antialiased p-4">
      
      {/* MAIN CARD: Frameless, High Contrast, Shadow */}
      <div className="w-full max-w-[450px] h-[95vh] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden relative ring-1 ring-slate-200">
        
        {/* HEADER: Clinical Blue Gradient */}
        <header className="h-20 bg-gradient-to-r from-[#1e40af] to-[#3b82f6] flex items-center justify-between px-6 shadow-md z-10 shrink-0">
             <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center text-white border border-white/30">
                    <Activity size={22} />
                </div>
                <div>
                    <h1 className="text-xl font-bold text-white tracking-wide">MediAssist</h1>
                    <span className="text-xs text-blue-100 font-medium flex items-center gap-1.5">
                        <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span> 
                        Secure Connection
                    </span>
                </div>
             </div>
             <Link to="/dashboard" className="p-2.5 bg-white/10 rounded-lg text-white hover:bg-white/20 transition-all duration-200 border border-white/10" title="Go to Dashboard">
                <LayoutDashboard size={20}/>
             </Link>
        </header>

        {/* CHAT MESSAGES AREA */}
        <main ref={chatContainerRef} className="flex-1 overflow-y-auto p-5 space-y-6 bg-[#F8FAFC]">
          
          {/* Intro Timestamp */}
          <div className="flex justify-center">
            <span className="px-3 py-1 bg-slate-200 text-slate-500 text-[11px] font-semibold rounded-full uppercase tracking-wider">
                Today
            </span>
          </div>

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
              
              {/* Text Bubble */}
              {msg.text && (
                <div className={`max-w-[80%] px-5 py-3.5 text-[15px] leading-relaxed shadow-sm relative
                    ${msg.sender === "user" 
                        ? "bg-[#1e40af] text-white rounded-2xl rounded-tr-none" 
                        : "bg-white text-slate-800 border border-slate-200 rounded-2xl rounded-tl-none"
                    }`}>
                   {renderMessageText(msg.text)}
                </div>
              )}

              {/* Bot Icon for context (Optional) */}
              {msg.sender === 'bot' && idx === messages.length - 1 && !msg.buttons && (
                  <span className="text-[10px] text-slate-400 mt-1 ml-1">AI Assistant</span>
              )}

              {/* Interactive Buttons */}
              {msg.buttons && (
                <div className="flex flex-wrap gap-2 mt-3">
                    {msg.buttons.map((btn, b) => (
                        <button key={b} onClick={() => { addMessage(btn.title, "user"); sendMessageToBackend(btn.payload); }} 
                            className="px-4 py-2 bg-white border border-[#bfdbfe] text-[#1e40af] rounded-lg text-sm font-semibold shadow-sm hover:bg-[#eff6ff] hover:border-[#1e40af] transition-all duration-200 active:scale-95">
                            {btn.title}
                        </button>
                    ))}
                </div>
              )}
            </div>
          ))}
          
          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex items-center gap-1 ml-1 bg-white border border-slate-200 px-4 py-3 rounded-2xl rounded-tl-none w-fit shadow-sm">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-75"></div>
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce delay-150"></div>
            </div>
          )}
        </main>

        {/* INPUT AREA */}
        <div className="bg-white border-t border-slate-200 p-5 shrink-0 z-10 relative">
           
           {/* Upload Modal (Floating) */}
           {showUpload && (
            <div className="absolute bottom-20 left-5 right-5 bg-white p-4 rounded-xl shadow-xl border border-slate-200 animate-in slide-in-from-bottom-5 z-20">
                <div className="flex justify-between items-center mb-3 pb-2 border-b border-slate-100">
                    <span className="font-bold text-sm text-slate-700 flex items-center gap-2">
                        <UploadCloud size={18} className="text-[#1e40af]"/> Upload Document
                    </span>
                    <button onClick={() => setShowUpload(false)} className="text-slate-400 hover:text-slate-600 transition"><X size={18}/></button>
                </div>
                <input type="file" onChange={handleFileUpload} className="block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-xs file:font-bold file:bg-[#eff6ff] file:text-[#1e40af] hover:file:bg-[#dbeafe] cursor-pointer"/>
            </div>
           )}
           
           {/* Options Picker (Floating) */}
           {showPicker && (
            <div className="absolute bottom-20 left-5 right-5 bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-in slide-in-from-bottom-5 z-20">
               <div className="flex justify-between p-3 bg-slate-50 border-b border-slate-100">
                   <span className="font-bold text-xs text-slate-500 uppercase tracking-wider flex gap-2 items-center"><Calendar size={14}/> Select Option</span>
                   <button onClick={() => setShowPicker(false)}><X size={16} className="text-slate-400 hover:text-slate-600"/></button>
               </div>
               <div className="p-3 flex flex-wrap justify-center gap-2 max-h-48 overflow-y-auto">
                  {pickerType === 'calendar' ? <Flatpickr options={{ inline: true, minDate: "today" }} onChange={handleDateSelect} /> : 
                   pickerOptions.map(t => <button key={t} onClick={() => {addMessage(t, "user"); sendMessageToBackend(t)}} className="px-4 py-2 bg-slate-50 border border-slate-200 rounded-md text-sm font-medium text-slate-700 hover:bg-[#1e40af] hover:text-white hover:border-[#1e40af] transition-colors">{t}</button>)}
               </div>
            </div>
           )}
           
           {/* Main Input Field */}
           <form onSubmit={handleSend} className="flex gap-3 items-center">
            <button type="button" onClick={() => setShowUpload(true)} className="w-11 h-11 bg-slate-100 rounded-full flex items-center justify-center text-slate-500 hover:bg-[#eff6ff] hover:text-[#1e40af] transition-colors shadow-sm">
                <Paperclip size={20} />
            </button>
            <div className="flex-1 relative">
                <input 
                    type="text" 
                    value={input} 
                    onChange={(e) => setInput(e.target.value)} 
                    placeholder="Type your health query..." 
                    className="w-full bg-slate-50 border border-slate-200 text-slate-800 text-sm rounded-full px-5 py-3 focus:outline-none focus:ring-2 focus:ring-[#1e40af] focus:border-transparent transition-all placeholder:text-slate-400"
                />
            </div>
            <button type="submit" disabled={!input.trim()} 
                className={`w-11 h-11 rounded-full flex items-center justify-center text-white shadow-md transition-all duration-200 
                ${input.trim() ? "bg-[#1e40af] hover:bg-[#1e3a8a] hover:scale-105" : "bg-slate-300 cursor-not-allowed"}`}>
                <Send size={20} className={input.trim() ? "ml-0.5" : ""} />
            </button>
          </form>
          
          <div className="text-center mt-3">
             <span className="text-[10px] text-slate-400 flex items-center justify-center gap-1">
                <ShieldCheck size={10} /> Encrypted & HIPAA Compliant
             </span>
          </div>
        </div>

      </div>
    </div>
  );
};

export default ChatbotPage;