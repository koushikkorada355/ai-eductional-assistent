import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { login } from '../../features/auth/authSlice.js';
import AuthLayout, { AuthSwitch, EyeIcon } from './AuthLayout.jsx';
import './Auth.css';

const EMAIL_RE = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

export default function Login() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const { status, error } = useSelector((s) => s.auth);
  const [email, setEmail] = useState(location.state?.email || '');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({});
  const [justRegistered] = useState(!!location.state?.justRegistered);

  const loading = status === 'loading';
  const emailError =
    touched.email && !email.trim()
      ? 'Enter your email address.'
      : touched.email && !EMAIL_RE.test(email.trim())
        ? 'That email address does not look right.'
        : null;
  const passwordError = touched.password && !password ? 'Enter your password.' : null;
  const invalid = !email.trim() || !EMAIL_RE.test(email.trim()) || !password;

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (invalid || loading) return;
    const r = await dispatch(login({ email: email.trim(), password }));
    if (r.meta.requestStatus === 'fulfilled') navigate('/', { replace: true });
  };

  return (
    <AuthLayout
      eyebrow="AI Study Companion"
      title="Welcome back to your learning space."
      sub="Your projects, progress, and learning context are ready when you are."
      footer={<AuthSwitch to="/register" text="New to AI Study Companion?" label="Create an account" />}
    >
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <h2 className="auth-title">Log in</h2>
        <p className="auth-caption">Pick up right where you left off.</p>
        {justRegistered && (
          <div className="auth-success" role="status">
            Account created. Log in to start learning.
          </div>
        )}
        <form onSubmit={submit} noValidate className="auth-form">
          <label className="auth-field">
            <span className="auth-label">Email</span>
            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, email: true }))}
              autoComplete="email"
              aria-invalid={!!emailError}
              className={emailError ? 'auth-input-error' : ''}
            />
            {emailError && <span className="auth-field-error">{emailError}</span>}
          </label>
          <label className="auth-field">
            <span className="auth-label">Password</span>
            <span className="auth-password-wrap">
              <input
                placeholder="Enter your password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                autoComplete="current-password"
                aria-invalid={!!passwordError}
                className={passwordError ? 'auth-input-error' : ''}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                aria-pressed={showPassword}
                className="auth-eye"
              >
                <EyeIcon off={showPassword} />
              </button>
            </span>
            {passwordError && <span className="auth-field-error">{passwordError}</span>}
          </label>
          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}
          <motion.button
            type="submit"
            whileTap={{ scale: 0.98 }}
            disabled={loading}
            className="auth-submit"
          >
            {loading && <span className="auth-spinner" aria-hidden="true" />}
            {loading ? 'Logging you in…' : 'Log in'}
          </motion.button>
        </form>
      </motion.div>
    </AuthLayout>
  );
}
