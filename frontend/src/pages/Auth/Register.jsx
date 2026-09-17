import { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { register } from '../../features/auth/authSlice.js';
import AuthLayout, { AuthSwitch, EyeIcon } from './AuthLayout.jsx';
import './Auth.css';

const EMAIL_RE = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;

export default function Register() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { status, error } = useSelector((s) => s.auth);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState({});

  const loading = status === 'loading';
  const nameError =
    touched.name && name.trim().length < 2 ? 'Tell us your name (at least 2 characters).' : null;
  const emailError =
    touched.email && !email.trim()
      ? 'Enter your email address.'
      : touched.email && !EMAIL_RE.test(email.trim())
        ? 'That email address does not look right.'
        : null;
  const passwordError =
    touched.password && password.length < 6 ? 'Use at least 6 characters for your password.' : null;
  const confirmError =
    touched.confirm && confirm !== password ? 'Passwords do not match yet.' : null;
  const invalid =
    name.trim().length < 2 ||
    !email.trim() ||
    !EMAIL_RE.test(email.trim()) ||
    password.length < 6 ||
    confirm !== password;

  const submit = async (e) => {
    e.preventDefault();
    setTouched({ name: true, email: true, password: true, confirm: true });
    if (invalid || loading) return;
    const r = await dispatch(register({ name: name.trim(), email: email.trim(), password }));
    if (r.meta.requestStatus === 'fulfilled') {
      navigate('/login', { state: { email: email.trim(), justRegistered: true } });
    }
  };

  return (
    <AuthLayout
      eyebrow="Begin your journey"
      title="Start your learning space."
      sub="Bring your materials, questions, and practice together in one connected learning journey."
      footer={<AuthSwitch to="/login" text="Already have an account?" label="Log in" />}
    >
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }}>
        <h2 className="auth-title">Create account</h2>
        <p className="auth-caption">Your first space is a minute away.</p>
        <form onSubmit={submit} noValidate className="auth-form">
          <label className="auth-field">
            <span className="auth-label">Name</span>
            <input
              type="text"
              placeholder="What should we call you?"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, name: true }))}
              autoComplete="name"
              maxLength={120}
              aria-invalid={!!nameError}
              className={nameError ? 'auth-input-error' : ''}
            />
            {nameError && <span className="auth-field-error">{nameError}</span>}
          </label>
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
          <div className="auth-row">
            <label className="auth-field">
              <span className="auth-label">Password</span>
              <span className="auth-password-wrap">
                <input
                  placeholder="6+ characters"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                  autoComplete="new-password"
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
            <label className="auth-field">
              <span className="auth-label">Confirm password</span>
              <input
                placeholder="Repeat password"
                type={showPassword ? 'text' : 'password'}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, confirm: true }))}
                autoComplete="new-password"
                aria-invalid={!!confirmError}
                className={confirmError ? 'auth-input-error' : ''}
              />
              {confirmError && <span className="auth-field-error">{confirmError}</span>}
            </label>
          </div>
          {error && (
            <div className="auth-error" role="alert">
              {error === 'Email already registered'
                ? 'An account with this email already exists. Try logging in instead.'
                : error}
            </div>
          )}
          <motion.button
            type="submit"
            whileTap={{ scale: 0.98 }}
            disabled={loading}
            className="auth-submit"
          >
            {loading && <span className="auth-spinner" aria-hidden="true" />}
            {loading ? 'Creating your space…' : 'Create account'}
          </motion.button>
        </form>
      </motion.div>
    </AuthLayout>
  );
}
