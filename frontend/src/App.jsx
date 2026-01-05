import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import ChatbotPage from './pages/ChatbotPage';
import DashboardPage from './pages/DashboardPage';

function App() {
  return (
    <Router>
      <Routes>
        {/* Patient View (The Chatbot) */}
        <Route path="/" element={<ChatbotPage />} />
        
        {/* Doctor/Admin View (The Dashboard) */}
        <Route path="/dashboard" element={<DashboardPage />} />
      </Routes>
    </Router>
  );
}

export default App;