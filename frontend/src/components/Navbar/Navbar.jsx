import { useState } from 'react';
import { useDispatch } from 'react-redux';
import { useNavigate } from 'react-router-dom';
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
      <div className="navbar-brand" onClick={() => navigate('/')}>AI Study Companion</div>
      <div className="navbar-right">
        <div className="profile-wrap">
          <button className="profile-btn" onClick={() => setOpen((v) => !v)}>Profile</button>
          {open && (
            <div className="profile-menu">
              <button onClick={onLogout}>Logout</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
