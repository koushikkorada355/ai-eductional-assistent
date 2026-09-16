import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { login, register } from '../../features/auth/authSlice.js';
import './Auth.css';

export default function Auth() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { status, error } = useSelector((s) => s.auth);
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = async (e) => {
    e.preventDefault();
    if (mode === 'login') {
      const r = await dispatch(login({ email, password }));
      if (r.meta.requestStatus === 'fulfilled') navigate('/');
    } else {
      const r = await dispatch(register({ email, password }));
      if (r.meta.requestStatus === 'fulfilled') setMode('login');
    }
  };

  return (
    <div className="auth-page">
      <motion.div className="auth-card" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h2>{mode === 'login' ? 'Welcome back' : 'Create account'}</h2>
        <form onSubmit={submit}>
          <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          {error && <div className="auth-error">{error}</div>}
          <button type="submit">{status === 'loading' ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}</button>
        </form>
        <button className="link" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Need an account? Register' : 'Have an account? Login'}
        </button>
      </motion.div>
    </div>
  );
}
