import { Link } from 'react-router-dom';

/* Shared authentication identity: brand panel with the
 * Learn → Practice → Measure → Grow journey + form card slot.
 * Login and Register render inside the same shell. */

const JOURNEY = [
  {
    id: 'Learn',
    text: 'Upload materials, chat with a tutor grounded in your PDFs',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 2.5 2.5 5 10 7.5 17.5 5 10 2.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M4 8.5V13c0 1.5 2.7 3 6 3s6-1.5 6-3V8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M16 6.5V12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: 'Practice',
    text: 'Adaptive quizzes that target your weak concepts',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10" cy="10" r="4.5" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="10" cy="10" r="1.3" fill="currentColor" />
      </svg>
    ),
  },
  {
    id: 'Measure',
    text: 'Mastery tracking that remembers what you struggle with',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M3 16.5h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M4.5 13.5 8 9.5l2.5 2.5 5-6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M12.5 5.5h3v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: 'Grow',
    text: 'Recommendations guide your next best study step',
    icon: (
      <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
        <path d="M10 17.5V10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M10 10C10 6.5 7.5 4.5 4 4.5c0 3.5 2.5 5.5 6 5.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M10 13.5c0-3.5 2.5-5.5 6-5.5 0 3.5-2.5 5.5-6 5.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
  },
];

export function EyeIcon({ off }) {
  return off ? (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M3.5 10S5.5 5.5 10 5.5 16.5 10 16.5 10 14.5 14.5 10 14.5 3.5 10 3.5 10Z" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4 4l12 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ) : (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M2.5 10S5 5 10 5s7.5 5 7.5 5-2.5 5-7.5 5S2.5 10 2.5 10Z" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="10" cy="10" r="2.2" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export default function AuthLayout({ eyebrow, title, sub, children, footer }) {
  return (
    <div className="auth-page">
      <div className="auth-shell">
        <aside className="auth-brand" aria-label="About AI Study Companion">
          <div className="auth-brand-mark">
            <span className="auth-logo">A</span>
            <span className="auth-brand-name">AI Study Companion</span>
          </div>
          <p className="auth-eyebrow">{eyebrow}</p>
          <h1 className="auth-headline">{title}</h1>
          <p className="auth-sub">{sub}</p>
          <ol className="auth-journey">
            {JOURNEY.map((step, i) => (
              <li key={step.id} className="auth-journey-step">
                <span className="auth-journey-rail" aria-hidden="true">
                  <span className="auth-journey-icon">{step.icon}</span>
                  {i < JOURNEY.length - 1 && <span className="auth-journey-line" />}
                </span>
                <span className="auth-journey-text">
                  <strong>{step.id}</strong>
                  <span>{step.text}</span>
                </span>
              </li>
            ))}
          </ol>
        </aside>
        <main className="auth-card">
          {children}
          {footer && <div className="auth-card-footer">{footer}</div>}
        </main>
      </div>
      <p className="auth-mobile-note">
        Learn <span aria-hidden="true">→</span> Practice <span aria-hidden="true">→</span> Measure{' '}
        <span aria-hidden="true">→</span> Grow
      </p>
    </div>
  );
}

export function AuthSwitch({ to, label, text }) {
  return (
    <p className="auth-switch">
      {text}{' '}
      <Link to={to} className="auth-switch-link">
        {label}
      </Link>
    </p>
  );
}
