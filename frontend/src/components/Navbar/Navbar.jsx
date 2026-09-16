import { useState } from 'react';
import { useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { logout } from '../../features/auth/authSlice.js';
import './Navbar.css';

export default function Navbar() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const onLogout = () => {
    dispatch(logout());
    navigate('/login');
  };
  return (
    <header className="navbar">
      <div className="navbar-brand" onClick={() => navigate('/')}>
        <span className="brand-mark">A</span>
        <span className="brand-text">AI Study <span>Companion</span></span>
      </div>
      <div className="navbar-right">
        <div className="profile-wrap">
          <button className="profile-btn" onClick={() => setOpen((v) => !v)}>
            <span className="avatar">U</span>
            Profile
          </button>
          <AnimatePresence>
            {open && (
              <motion.div
                className="profile-menu"
                initial={{ opacity: 0, y: -6, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.98 }}
                transition={{ duration: 0.15 }}
              >
                <button onClick={onLogout}>Logout</button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
