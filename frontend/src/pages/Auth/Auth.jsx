import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { login, register } from '../../features/auth/authSlice.js';
import { IconBook, IconTarget, IconGraduation } from '../../components/icons/Icons.jsx';
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
      <motion.div
        className="auth-hero"
        initial={{ opacity: 0, x: -24 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1>Meet your persistent study partner.</h1>
        <p>Upload your materials, chat with a grounded AI tutor, take adaptive quizzes, and watch your mastery grow.</p>
        <div className="hero-points">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <span><IconBook size={26} /></span> Chat grounded strictly in your PDFs, with citations
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.32 }}>
            <span><IconTarget size={26} /></span> Adaptive quizzes that target your weak concepts
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.44 }}>
            <span><IconGraduation size={26} /></span> Mastery tracking that remembers what you struggle with
          </motion.div>
        </div>
      </motion.div>
      <motion.div
        className="auth-card"
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
      >
        <h2>{mode === 'login' ? 'Welcome back' : 'Create account'}</h2>
        <p className="auth-sub muted">{mode === 'login' ? 'Pick up right where you left off.' : 'Start your learning journey today.'}</p>
        <form onSubmit={submit}>
          <label>Email
            <input placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>Password
            <input placeholder="••••••••" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <div className="auth-error">{error}</div>}
          <motion.button type="submit" whileTap={{ scale: 0.98 }}>
            {status === 'loading' ? 'Please wait...' : mode === 'login' ? 'Login' : 'Register'}
          </motion.button>
        </form>
        <button className="link" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Need an account? Register' : 'Have an account? Login'}
        </button>
      </motion.div>
    </div>
  );
}
