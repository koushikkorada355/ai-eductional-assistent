import { useEffect, useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import Navbar from './components/Navbar/Navbar.jsx';
import Sidebar from './components/Sidebar/Sidebar.jsx';
import Login from './pages/Auth/Login.jsx';
import Register from './pages/Auth/Register.jsx';
import Spaces from './pages/Spaces/Spaces.jsx';
import Home from './pages/Home/Home.jsx';
import GlobalAnalytics from './pages/GlobalAnalytics/GlobalAnalytics.jsx';
import Admin from './pages/Admin/Admin.jsx';
import ProjectWorkspace from './pages/ProjectWorkspace/ProjectWorkspace.jsx';
import { fetchMe } from './features/auth/authApi.js';

function Shell({ children, isAdmin }) {
  const [navOpen, setNavOpen] = useState(false);
  // Desktop sidebar collapse (mobile drawer unaffected). Persisted.
  const [sideCollapsed, setSideCollapsed] = useState(() => {
    try {
      return localStorage.getItem('app-sidebar:collapsed') === '1';
    } catch {
      return false;
    }
  });
  const toggleSidebar = () => {
    setSideCollapsed((v) => {
      try {
        localStorage.setItem('app-sidebar:collapsed', v ? '0' : '1');
      } catch {
        // private mode etc. — collapse still works for the session
      }
      return !v;
    });
  };
  return (
    <div className="min-h-screen bg-canvas">
      {/* Single primary navigation: full-height left sidebar owns brand + sections.
          The slim top header carries context (breadcrumb) + account only. */}
      <div className="flex min-h-screen">
        <Sidebar
          open={navOpen}
          onClose={() => setNavOpen(false)}
          isAdmin={isAdmin}
          collapsed={sideCollapsed}
          onCollapse={toggleSidebar}
          onExpand={toggleSidebar}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Navbar onMenuToggle={() => setNavOpen((v) => !v)} />
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const token = useSelector((s) => s.auth.token);
  const [me, setMe] = useState(null);

  useEffect(() => {
    if (token) {
      fetchMe().then(setMe).catch(() => setMe(null));
    } else {
      setMe(null);
    }
  }, [token]);

  const isAdmin = me?.role === 'admin';
  const guard = (el) => (token ? el : <Navigate to="/login" replace />);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={guard(<Shell isAdmin={isAdmin}><Home /></Shell>)} />
      <Route path="/spaces" element={guard(<Shell isAdmin={isAdmin}><Spaces /></Shell>)} />
      <Route path="/analytics" element={guard(<Shell isAdmin={isAdmin}><GlobalAnalytics /></Shell>)} />
      <Route
        path="/admin"
        element={token ? (isAdmin ? <Shell isAdmin={isAdmin}><Admin /></Shell> : <Navigate to="/" replace />) : <Navigate to="/login" replace />}
      />
      <Route
        path="/spaces/:spaceId/projects/:projectId"
        element={guard(<Shell isAdmin={isAdmin}><ProjectWorkspace /></Shell>)}
      />
      <Route
        path="/spaces/:spaceId/projects/:projectId/tutor"
        element={guard(<Shell isAdmin={isAdmin}><ProjectWorkspace /></Shell>)}
      />
      <Route
        path="/spaces/:spaceId/projects/:projectId/tutor/:conversationId"
        element={guard(<Shell isAdmin={isAdmin}><ProjectWorkspace /></Shell>)}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
