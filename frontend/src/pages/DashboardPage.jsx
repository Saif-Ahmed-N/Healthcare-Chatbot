import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  Stethoscope, Microscope, Pill, LogOut, Activity, Calendar, 
  Clock, CheckCircle, XCircle, ChevronRight, AlertCircle, RefreshCw
} from 'lucide-react';

const API_URL = "http://localhost:8000";

const DashboardPage = () => {
  const [activeRole, setActiveRole] = useState(null); // 'doctor', 'lab', 'pharmacy'
  const [doctorId, setDoctorId] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [records, setRecords] = useState([]);
  const [dashboardTitle, setDashboardTitle] = useState("");
  const [loading, setLoading] = useState(false);

  // --- LOGIN HANDLER ---
  const handleLogin = async (role) => {
    setLoading(true);
    try {
        let url = "";
        if (role === 'doctor') {
            if (!doctorId) { alert("Please enter Doctor ID"); setLoading(false); return; }
            url = `${API_URL}/appointments/dashboard/doctor/${doctorId}`;
        } else if (role === 'lab') {
            url = `${API_URL}/appointments/dashboard/lab`;
        } else if (role === 'pharmacy') {
            url = `${API_URL}/appointments/dashboard/pharmacy`;
        }

        const resp = await axios.get(url);
        if (resp.status === 200) {
            setRecords(resp.data.records);
            setDashboardTitle(resp.data.role);
            setActiveRole(role);
            setIsLoggedIn(true);
        }
    } catch (err) {
        alert("Login failed. Check ID or Connection.");
    } finally {
        setLoading(false);
    }
  };

  // --- STATUS TOGGLE HANDLER (Reversible Actions) ---
  const handleStatusUpdate = async (id, type, currentStatus) => {
      let newStatus = currentStatus;
      let url = "";

      // LOGIC: Toggle states
      if (type === 'Appointment') {
          url = `${API_URL}/appointments/update/appointment/${id}`;
          newStatus = (currentStatus === 'Cancelled') ? 'Scheduled' : 'Cancelled';
      }
      else if (type === 'Lab Test') {
          url = `${API_URL}/appointments/update/lab/${id}`;
          newStatus = (currentStatus === 'Completed') ? 'Pending' : 'Completed';
      }
      else if (type === 'Pharmacy') {
          url = `${API_URL}/appointments/update/pharmacy/${id}`;
          newStatus = (currentStatus === 'Ready') ? 'Processing' : 'Ready';
      }

      try {
          await axios.put(url, { status: newStatus });
          // Optimistic UI Update
          setRecords(prev => prev.map(r => r.id === id ? { ...r, status: newStatus } : r));
      } catch (e) {
          alert("Update failed. Backend might be offline.");
      }
  };

  // --- REAL-TIME SYNC (5s Loop) ---
  useEffect(() => {
    if (!isLoggedIn) return;
    const interval = setInterval(() => {
        let url = "";
        if (activeRole === 'doctor') url = `${API_URL}/appointments/dashboard/doctor/${doctorId}`;
        else if (activeRole === 'lab') url = `${API_URL}/appointments/dashboard/lab`;
        else if (activeRole === 'pharmacy') url = `${API_URL}/appointments/dashboard/pharmacy`;

        axios.get(url).then(resp => {
            if (resp.status === 200) setRecords(resp.data.records);
        }).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [isLoggedIn, activeRole, doctorId]);

  // ================= LOGIN SCREEN (Premium Glass) =================
  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-[#F2F2F7] flex items-center justify-center p-6 font-sans">
        <div className="max-w-4xl w-full grid grid-cols-1 md:grid-cols-2 gap-8">
            
            {/* Branding */}
            <div className="flex flex-col justify-center space-y-6 p-6">
                <div className="w-20 h-20 bg-white rounded-[1.5rem] shadow-xl flex items-center justify-center">
                    <Activity className="text-[#0071E3] w-10 h-10" />
                </div>
                <div>
                    <h1 className="text-5xl font-bold tracking-tight text-[#1D1D1F]">MediAssist <span className="text-[#0071E3]">Pro</span></h1>
                    <p className="text-xl text-[#86868B] font-medium mt-2">Secure Enterprise Portal</p>
                </div>
            </div>

            {/* Login Cards */}
            <div className="space-y-4">
                {/* DOCTOR */}
                <div className="bg-white/80 backdrop-blur-xl p-6 rounded-[2rem] shadow-sm hover:shadow-xl transition-all duration-300 border border-white group focus-within:ring-2 focus-within:ring-[#0071E3]/30">
                    <div className="flex items-center gap-4 mb-4">
                        <div className="p-3 bg-blue-100 rounded-2xl text-blue-600"><Stethoscope/></div>
                        <h3 className="text-xl font-semibold text-[#1D1D1F]">Doctor Login</h3>
                    </div>
                    <div className="flex gap-2">
                        <input 
                          type="text" placeholder="Enter ID (e.g. 1)" 
                          className="flex-1 px-4 py-3 bg-[#F5F5F7] rounded-xl border-none outline-none focus:ring-0 text-[#1D1D1F] font-medium placeholder-gray-400"
                          value={doctorId} onChange={(e) => setDoctorId(e.target.value)}
                        />
                        <button onClick={() => handleLogin('doctor')} disabled={loading} className="px-6 bg-[#0071E3] text-white rounded-xl font-bold hover:bg-blue-600 transition-colors shadow-lg shadow-blue-500/30">
                           Go
                        </button>
                    </div>
                </div>

                {/* LAB */}
                <button onClick={() => handleLogin('lab')} disabled={loading} className="w-full text-left bg-white/80 backdrop-blur-xl p-6 rounded-[2rem] shadow-sm hover:shadow-xl transition-all duration-300 border border-white flex items-center justify-between group active:scale-[0.98]">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-purple-100 rounded-2xl text-purple-600"><Microscope/></div>
                        <div>
                            <h3 className="text-xl font-semibold text-[#1D1D1F]">Lab Technician</h3>
                            <p className="text-sm text-[#86868B]">Manage test results</p>
                        </div>
                    </div>
                    <div className="w-10 h-10 rounded-full bg-[#F5F5F7] flex items-center justify-center group-hover:bg-[#0071E3] group-hover:text-white transition-colors">
                        <ChevronRight size={20}/>
                    </div>
                </button>

                {/* PHARMACY */}
                <button onClick={() => handleLogin('pharmacy')} disabled={loading} className="w-full text-left bg-white/80 backdrop-blur-xl p-6 rounded-[2rem] shadow-sm hover:shadow-xl transition-all duration-300 border border-white flex items-center justify-between group active:scale-[0.98]">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-green-100 rounded-2xl text-green-600"><Pill/></div>
                        <div>
                            <h3 className="text-xl font-semibold text-[#1D1D1F]">Pharmacy</h3>
                            <p className="text-sm text-[#86868B]">Fulfill prescriptions</p>
                        </div>
                    </div>
                    <div className="w-10 h-10 rounded-full bg-[#F5F5F7] flex items-center justify-center group-hover:bg-[#0071E3] group-hover:text-white transition-colors">
                        <ChevronRight size={20}/>
                    </div>
                </button>
            </div>
        </div>
      </div>
    );
  }

  // ================= DASHBOARD MAIN =================
  return (
    <div className="min-h-screen bg-[#F5F5F7] font-sans text-[#1D1D1F] pb-20">
      
      {/* Navbar */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200/50 px-6 py-4 flex justify-between items-center transition-all">
        <div className="flex items-center gap-4">
            <div className={`p-2.5 rounded-2xl text-white shadow-lg shadow-blue-500/20 
                ${activeRole === 'doctor' ? 'bg-[#0071E3]' : activeRole === 'lab' ? 'bg-purple-600' : 'bg-green-600'}`}>
                {activeRole === 'doctor' ? <Stethoscope size={22}/> : activeRole === 'lab' ? <Microscope size={22}/> : <Pill size={22}/>}
            </div>
            <div>
                <h1 className="text-lg font-bold leading-none tracking-tight">{dashboardTitle}</h1>
                <p className="text-xs text-[#86868B] font-medium uppercase mt-1 tracking-wide">Live Console</p>
            </div>
        </div>
        <button onClick={() => window.location.reload()} className="p-2.5 bg-gray-100 hover:bg-red-50 text-gray-500 hover:text-red-500 rounded-full transition-all duration-300">
            <LogOut size={20}/>
        </button>
      </header>

      <main className="max-w-5xl mx-auto p-6 space-y-8">
        
        {/* Stats */}
        <div className="flex items-center justify-between">
            <h2 className="text-3xl font-bold tracking-tight">Overview</h2>
            <div className="bg-white/60 backdrop-blur-lg px-5 py-2.5 rounded-full text-sm font-medium text-[#86868B] shadow-sm border border-white">
                Active Records: <span className="text-[#1D1D1F] font-bold ml-1">{records.length}</span>
            </div>
        </div>

        {/* Records Grid */}
        <div className="grid grid-cols-1 gap-5">
            {records.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-[#86868B] bg-white/50 rounded-[2rem] border border-dashed border-gray-300">
                    <AlertCircle size={40} className="mb-2 opacity-50"/>
                    <p>No active records found.</p>
                </div>
            ) : (
                records.map((rec) => (
                    <div key={rec.id} className="group bg-white rounded-[1.8rem] p-5 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.05)] border border-white hover:shadow-[0_20px_40px_-10px_rgba(0,0,0,0.1)] hover:scale-[1.01] transition-all duration-300 flex items-center justify-between">
                        
                        {/* Info */}
                        <div className="flex items-center gap-6">
                            <div className={`w-16 h-16 rounded-[1.2rem] flex items-center justify-center text-2xl shadow-inner
                                ${activeRole === 'doctor' ? 'bg-blue-50 text-blue-600' : activeRole === 'lab' ? 'bg-purple-50 text-purple-600' : 'bg-green-50 text-green-600'}`}>
                                {activeRole === 'doctor' ? <Calendar/> : activeRole === 'lab' ? <Microscope/> : <Pill/>}
                            </div>
                            
                            <div>
                                <h3 className="text-lg font-bold text-[#1D1D1F]">{rec.title}</h3>
                                <p className="text-[#86868B] text-sm font-medium">{rec.subtitle}</p>
                                <div className="flex items-center gap-3 mt-2.5 text-xs font-semibold text-[#86868B]">
                                    <span className="flex items-center gap-1.5 bg-[#F5F5F7] px-3 py-1.5 rounded-lg"><Calendar size={12}/> {rec.date}</span>
                                    <span className="flex items-center gap-1.5 bg-[#F5F5F7] px-3 py-1.5 rounded-lg"><Clock size={12}/> {rec.time}</span>
                                    {rec.extra && <span className="flex items-center gap-1.5 bg-blue-50 text-blue-600 px-3 py-1.5 rounded-lg">{rec.extra}</span>}
                                </div>
                            </div>
                        </div>

                        {/* Status & Reversible Actions */}
                        <div className="flex flex-col items-end gap-3">
                             <span className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wide shadow-sm
                                ${rec.status === 'Scheduled' || rec.status === 'Processing' || rec.status === 'Pending' ? 'bg-yellow-100 text-yellow-700' : 
                                  rec.status === 'Completed' || rec.status === 'Ready' ? 'bg-green-100 text-green-700' : 
                                  rec.status === 'Cancelled' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`}>
                                {rec.status}
                             </span>
                             
                             <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex gap-2">
                                
                                {/* DOCTOR ACTIONS */}
                                {activeRole === 'doctor' && (
                                    <button 
                                        onClick={() => handleStatusUpdate(rec.id, 'Appointment', rec.status)}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors
                                            ${rec.status === 'Cancelled' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}
                                    >
                                        {rec.status === 'Cancelled' ? <><RefreshCw size={14}/> Re-Schedule</> : <><XCircle size={14}/> Cancel</>}
                                    </button>
                                )}

                                {/* LAB ACTIONS */}
                                {activeRole === 'lab' && (
                                    <button 
                                        onClick={() => handleStatusUpdate(rec.id, 'Lab Test', rec.status)}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors
                                            ${rec.status === 'Completed' ? 'bg-yellow-50 text-yellow-600 hover:bg-yellow-100' : 'bg-green-50 text-green-600 hover:bg-green-100'}`}
                                    >
                                        {rec.status === 'Completed' ? 'Mark Pending' : 'Mark Complete'}
                                    </button>
                                )}

                                {/* PHARMACY ACTIONS */}
                                {activeRole === 'pharmacy' && (
                                    <button 
                                        onClick={() => handleStatusUpdate(rec.id, 'Pharmacy', rec.status)}
                                        className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors
                                            ${rec.status === 'Ready' ? 'bg-yellow-50 text-yellow-600 hover:bg-yellow-100' : 'bg-blue-50 text-blue-600 hover:bg-blue-100'}`}
                                    >
                                        {rec.status === 'Ready' ? 'Mark Processing' : 'Mark Ready'}
                                    </button>
                                )}
                             </div>
                        </div>
                    </div>
                ))
            )}
        </div>
      </main>
    </div>
  );
};

export default DashboardPage;