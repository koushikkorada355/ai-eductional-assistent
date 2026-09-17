/* Shared Tailwind-based UI primitives. Same palette as the design tokens —
 * primary #4338ca, accent #047857, canvas #edf0f6 — no new colors. */

export function PageHeader({ eyebrow, title, sub, actions }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && (
          <span className="mb-1 block text-[11px] font-bold uppercase tracking-[0.06em] text-primary">
            {eyebrow}
          </span>
        )}
        <h1 className="font-display text-[22px] font-bold text-heading">{title}</h1>
        {sub && <p className="mt-1 max-w-2xl text-sm text-muted">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({ value, label, tone }) {
  const tones = { accent: 'text-primary', up: 'text-accent', down: 'text-danger' };
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-card border border-line bg-surface p-5 shadow-sm">
      <span className={`truncate font-display text-2xl font-bold text-heading ${tones[tone] || ''}`}>
        {value}
      </span>
      <span className="text-xs font-medium text-muted">{label}</span>
    </div>
  );
}

const STATUS_TONES = {
  ready: 'bg-accent-soft text-accent',
  perfect: 'bg-accent-soft text-accent',
  strong: 'bg-accent-soft text-accent',
  submitted: 'bg-info-soft text-info',
  pass: 'bg-info-soft text-info',
  generating: 'bg-warning-soft text-warning',
  evaluating: 'bg-warning-soft text-warning',
  processing: 'bg-warning-soft text-warning',
  failed: 'bg-danger-soft text-danger',
  weak: 'bg-danger-soft text-danger',
  fail: 'bg-danger-soft text-danger',
  learning: 'bg-primary-soft text-primary',
  draft: 'bg-canvas text-muted',
  queued: 'bg-canvas text-muted',
};

export function StatusBadge({ status, children, tone }) {
  const label = children ?? status;
  const cls = tone
    ? { success: 'bg-accent-soft text-accent', info: 'bg-info-soft text-info', warn: 'bg-warning-soft text-warning', danger: 'bg-danger-soft text-danger', muted: 'bg-canvas text-muted', primary: 'bg-primary-soft text-primary' }[tone]
    : STATUS_TONES[String(status || '').toLowerCase()];
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${cls || 'bg-canvas text-muted'}`}>
      {label}
    </span>
  );
}

export function EmptyState({ title, body, actions }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-card border border-line bg-surface p-8 text-center text-[13px] text-muted shadow-sm">
      {title && <h3 className="font-display text-[15px] font-semibold text-heading">{title}</h3>}
      {body && <p className="max-w-[460px]">{body}</p>}
      {actions && <div className="mt-1 flex flex-wrap justify-center gap-2">{actions}</div>}
    </div>
  );
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3" role="status" aria-label={label || 'Loading'}>
      <span className="spinner" aria-hidden="true" />
      {label && <span className="text-sm text-muted">{label}</span>}
    </div>
  );
}

export function ProgressBar({ value, className }) {
  const pct = Math.min(100, Math.max(0, Number(value) || 0));
  return (
    <div className={`h-1.5 overflow-hidden rounded-full bg-canvas ${className || ''}`}>
      <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Card({ children, className }) {
  return (
    <div className={`rounded-card border border-line bg-surface p-6 shadow-sm ${className || ''}`}>
      {children}
    </div>
  );
}
