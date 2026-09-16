import { Routes, Route, Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import Navbar from './components/Navbar/Navbar.jsx';
import Sidebar from './components/Sidebar/Sidebar.jsx';
import Auth from './pages/Auth/Auth.jsx';
import Dashboard from './pages/Dashboard/Dashboard.jsx';
import ProjectWorkspace from './pages/ProjectWorkspace/ProjectWorkspace.jsx';
import './App.css';

function Shell({ children }) {
  return (
    <div className="app-shell">
      <Navbar />
      <div className="app-body">
        <Sidebar />
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}

export default function App() {
  const token = useSelector((s) => s.auth.token);
  return (
    <Routes>
      <Route path="/login" element={<Auth />} />
      <Route
        path="/"
        element={token ? <Shell><Dashboard /></Shell> : <Navigate to="/login" replace />}
      />
      <Route
        path="/spaces/:spaceId/projects/:projectId"
        element={token ? <Shell><ProjectWorkspace /></Shell> : <Navigate to="/login" replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
