import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import {
  loadAdminOverview, loadAdminUsers, loadAdminUserDetail, loadAdminSpaces,
  loadAdminProjects, loadAdminActivity, loadAdminJobs,
  loadAdminEvaluations, loadAdminUsage, loadAdminHealth,
} from '../../features/analytics/analyticsSlice.js';
import { PageHeader, Stat, StatusBadge, EmptyState, ProgressBar } from '../../components/ui/ui.jsx';
import './Admin.css';

const TABS = [
  'Overview', 'Users', 'Spaces & Projects', 'Activity',
  'AI Usage', 'AI Evaluation', 'Processing', 'Health',
];

/* ---------- tiny SVG icon set (no emoji) ---------- */
const I = {
  users: (<svg viewBox="0 0 20 20" fill="none"><circle cx="7" cy="6.5" r="2.8" stroke="currentColor" strokeWidth="1.5" /><path d="M1.8 16.5c.6-3 2.8-4.5 5.2-4.5s4.6 1.5 5.2 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><circle cx="13.8" cy="7.5" r="2.2" stroke="currentColor" strokeWidth="1.5" /><path d="M14.5 12.3c2 .3 3.3 1.6 3.7 3.7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>),
  space: (<svg viewBox="0 0 20 20" fill="none"><path d="M2.5 6.5v7c0 1 .8 1.7 1.7 1.4l11-3.4c1.2-.4 1.2-2.1 0-2.5l-11-3.9c-.9-.3-1.7.4-1.7 1.4Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>),
  project: (<svg viewBox="0 0 20 20" fill="none"><path d="M3 5.5A1.5 1.5 0 0 1 4.5 4h4l1.5 2h5.5A1.5 1.5 0 0 1 17 7.5V14a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 14v-8.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>),
  chat: (<svg viewBox="0 0 20 20" fill="none"><path d="M3 4.5A1.5 1.5 0 0 1 4.5 3h11A1.5 1.5 0 0 1 17 4.5v7a1.5 1.5 0 0 1-1.5 1.5H8l-3.5 3v-3H4.5A1.5 1.5 0 0 1 3 11.5v-7Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>),
  quiz: (<svg viewBox="0 0 20 20" fill="none"><path d="M6 3h8a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.5" /><path d="M7.5 10l1.8 1.8L12.8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>),
  doc: (<svg viewBox="0 0 20 20" fill="none"><path d="M5 2.5h6L15.5 7v9.5a1 1 0 0 1-1 1h-9.5a1 1 0 0 1-1-1v-13a1 1 0 0 1 1-1Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M11 2.5V7.5h4.5" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>),
  cpu: (<svg viewBox="0 0 20 20" fill="none"><rect x="5.5" y="5.5" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5" /><path d="M8 2.5v3M12 2.5v3M8 14.5v3M12 14.5v3M2.5 8h3M2.5 12h3M14.5 8h3M14.5 12h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>),
  pulse: (<svg viewBox="0 0 20 20" fill="none"><path d="M2 10h4l2-5 3 10 2-5h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>),
};

function Kpi({ icon, value, label }) {
  return (
    <div className="ops-kpi">
      <span className="ops-kpi-icon" aria-hidden="true">{icon}</span>
      <span className="ops-kpi-body">
        <span className="ops-kpi-value">{value}</span>
        <span className="ops-kpi-label">{label}</span>
      </span>
    </div>
  );
}

function Card({ title, sub, actions, children, className }) {
  return (
    <section className={`ops-card ${className || ''}`}>
      {(title || actions) && (
        <header className="ops-card-head">
          <div>
            {title && <h3 className="ops-card-title">{title}</h3>}
            {sub && <p className="ops-card-sub">{sub}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

function Sparkline({ points }) {
  const data = (points || []).map((p) => p.count || 0);
  if (!data.length || Math.max(...data) === 0) {
    return <p className="ops-muted">No activity in the last 14 days.</p>;
  }
  const w = 560, h = 96, pad = 8;
  const max = Math.max(...data);
  const step = (w - pad * 2) / Math.max(1, data.length - 1);
  const pts = data.map((v, i) => `${(pad + i * step).toFixed(1)},${(h - pad - (v / max) * (h - pad * 2)).toFixed(1)}`).join(' ');
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="ops-spark" role="img" aria-label="Learning activity over the last 14 days">
        <polyline points={pts} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {data.map((v, i) => (
          <circle key={i} cx={pad + i * step} cy={h - pad - (v / max) * (h - pad * 2)} r="3" fill="var(--primary)">
            <title>{`${points[i].date}: ${v}`}</title>
          </circle>
        ))}
      </svg>
      <div className="ops-spark-axis">
        <span>{points[0]?.date}</span>
        <span>{points[points.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function BarRow({ label, value, total, tone }) {
  return (
    <div className="ops-bar-row">
      <span className="ops-bar-label">{label}</span>
      <div className="ops-bar-track">
        <div className={`ops-bar-fill ${tone || ''}`} style={{ width: `${Math.min(100, (value / Math.max(1, total)) * 100)}%` }} />
      </div>
      <span className="ops-bar-value">{value}</span>
    </div>
  );
}

const timeAgo = (d) => {
  if (!d) return '—';
  const t = new Date(d).getTime();
  if (Number.isNaN(t)) return '—';
  const mins = Math.floor((Date.now() - t) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h}h ago`;
  const days = Math.floor(h / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(d).toLocaleDateString();
};
const fmtDate = (d) => (d ? new Date(d).toLocaleDateString() : '—');

const HEALTH_TONE = { healthy: 'ok', degraded: 'warn', unavailable: 'bad' };
function HealthDot({ status }) {
  return <span className={`ops-dot ${HEALTH_TONE[status] || 'warn'}`} aria-hidden="true" />;
}

/* ================= OVERVIEW ================= */
function Overview({ ov }) {
  if (!ov) return <EmptyState title="No overview data" body="The platform has not recorded any activity yet." />;
  const tutor = ov.tutorInteractions || { total: 0, user: 0, assistant: 0 };
  const quiz = ov.quizAttempts || { quizzes: 0, questionsAnswered: 0 };
  const mats = ov.materials || ov.documents || { total: 0, byStatus: {} };
  return (
    <>
      <div className="ops-kpis">
        <Kpi icon={I.users} value={ov.users ?? 0} label="Total users" />
        <Kpi icon={I.pulse} value={ov.activeUsers ?? 0} label={`Active (30d)`} />
        <Kpi icon={I.space} value={ov.spaces ?? 0} label="Spaces" />
        <Kpi icon={I.project} value={ov.projects ?? 0} label="Projects" />
        <Kpi icon={I.chat} value={tutor.total ?? ov.messages ?? 0} label="Tutor interactions" />
        <Kpi icon={I.quiz} value={quiz.quizzes ?? 0} label="Quiz attempts" />
        <Kpi icon={I.doc} value={mats.total ?? 0} label="Materials uploaded" />
        <Kpi icon={I.cpu} value={ov.aiRequests ?? 0} label="AI requests" />
      </div>
      <div className="ops-grid-2">
        <Card title="Learning activity" sub="Messages, quizzes, uploads and signups per day">
          <Sparkline points={ov.activitySeries} />
        </Card>
        <Card title="User engagement" sub="How learners interact with the platform">
          <BarRow label="Learner questions" value={tutor.user || 0} total={Math.max(1, tutor.total)} />
          <BarRow label="Tutor answers" value={tutor.assistant || 0} total={Math.max(1, tutor.total)} tone="green" />
          <BarRow label="Quiz questions answered" value={quiz.questionsAnswered || 0} total={Math.max(1, (quiz.questionsAnswered || 0) + 1)} tone="blue" />
          <div className="ops-engagement-foot">
            <span><strong>{ov.concepts ?? 0}</strong> concepts tracked</span>
            <span><strong>{quiz.quizzes ?? 0}</strong> quizzes created</span>
          </div>
        </Card>
      </div>
      <div className="ops-grid-2">
        <Card title="Recent platform activity" sub="Latest events across all users">
          <ActivityList items={ov.recentActivity} compact />
        </Card>
        <Card title="Overall system status" sub="Live application health">
          <SystemList system={ov.system} />
        </Card>
      </div>
    </>
  );
}

function SystemList({ system }) {
  if (!system) return <p className="ops-muted">Status unavailable.</p>;
  const rows = [
    { name: 'Database', info: system.database },
    { name: 'API', info: system.uptime },
    { name: 'Redis', info: system.redis?.status || system.redis },
    { name: 'Workers', info: system.workers?.status || system.workers },
    { name: 'Document processing', info: system.documentProcessing?.status || system.documentProcessing },
  ];
  return (
    <ul className="ops-health-list">
      {rows.map((r) => {
        const status = typeof r.info === 'object' ? r.info.status : r.info;
        const detail = typeof r.info === 'object' ? r.info.detail : null;
        return (
          <li key={r.name}>
            <HealthDot status={status} />
            <span className="ops-health-name">{r.name}</span>
            <span className={`ops-health-status ${HEALTH_TONE[status] || ''}`}>{status || 'unknown'}</span>
            {detail && <span className="ops-health-detail">{detail}</span>}
          </li>
        );
      })}
    </ul>
  );
}

/* ================= USERS ================= */
function Users({ users, onOpen, detail, onClose }) {
  const [q, setQ] = useState('');
  const [role, setRole] = useState('all');
  const filtered = useMemo(() => (users || []).filter((u) => {
    const needle = q.trim().toLowerCase();
    const hit = !needle || (u.email || '').toLowerCase().includes(needle) || (u.name || '').toLowerCase().includes(needle);
    return hit && (role === 'all' || u.role === role);
  }), [users, q, role]);
  return (
    <>
      <Card
        title="User management"
        sub={`${filtered.length} of ${(users || []).length} users`}
        actions={
          <div className="ops-filters">
            <input
              type="text" placeholder="Search name or email…" value={q}
              onChange={(e) => setQ(e.target.value)} aria-label="Search users"
              className="ops-search"
            />
            <select value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter by role" className="ops-select">
              <option value="all">All roles</option>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        }
      >
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead>
              <tr>{['User', 'Role', 'Spaces', 'Projects', 'Last active', 'Joined'].map((h) => <th key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id} onClick={() => onOpen(u.id)} className="ops-row-clickable" tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter') onOpen(u.id); }}>
                  <td>
                    <span className="ops-user-cell">
                      <span className="ops-avatar">{((u.name || u.email) || '?')[0].toUpperCase()}</span>
                      <span><strong>{u.name || '—'}</strong><small>{u.email}</small></span>
                    </span>
                  </td>
                  <td><StatusBadge tone={u.role === 'admin' ? 'danger' : 'muted'}>{u.role}</StatusBadge></td>
                  <td>{u.spaces}</td>
                  <td>{u.projects}</td>
                  <td>{timeAgo(u.last_active)}</td>
                  <td>{fmtDate(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && <p className="ops-muted ops-pad">No users match this filter.</p>}
        </div>
      </Card>
      <AnimatePresence>
        {detail && (
          <motion.div className="ops-drawer-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
            <motion.div className="ops-drawer" initial={{ x: 60, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 60, opacity: 0 }}
              onClick={(e) => e.stopPropagation()} role="dialog" aria-label={`Learning journey for ${detail.email}`}>
              <div className="ops-drawer-head">
                <span className="ops-avatar ops-avatar-lg">{((detail.name || detail.email) || '?')[0].toUpperCase()}</span>
                <div>
                  <h3>{detail.name || detail.email}</h3>
                  <p className="ops-muted">{detail.email} · {detail.role} · joined {fmtDate(detail.created_at)}</p>
                </div>
                <button type="button" onClick={onClose} className="ops-icon-btn" aria-label="Close user detail">✕</button>
              </div>
              <div className="ops-drawer-kpis">
                <Stat value={detail.learning?.tutorMessages ?? 0} label="Tutor messages" />
                <Stat value={`${detail.learning?.averageMastery ?? 0}%`} label="Avg mastery" />
                <Stat value={detail.learning?.quizzes ?? 0} label="Quizzes" />
                <Stat value={detail.aiUsage?.assistantMessages ?? 0} label="AI answers" />
              </div>
              <h4>Spaces & projects</h4>
              {(detail.projects || []).length === 0 && <p className="ops-muted">No spaces or projects yet.</p>}
              <ul className="ops-plain-list">
                {(detail.projects || []).map((p) => (
                  <li key={p.id}>
                    <strong>{p.name}</strong>
                    <span className="ops-muted">{p.space} · {p.progress}% mastery · active {timeAgo(p.last_active)}</span>
                  </li>
                ))}
              </ul>
              <h4>Quiz & assessment activity</h4>
              {(detail.quizzes || []).length === 0 && <p className="ops-muted">No quiz attempts yet.</p>}
              <ul className="ops-plain-list">
                {(detail.quizzes || []).slice(0, 8).map((x) => (
                  <li key={x.id}>
                    <strong>{x.name}</strong>
                    <span className="ops-muted">{x.project} · {x.status}{x.average != null ? ` · ${x.average}%` : ''}</span>
                  </li>
                ))}
              </ul>
              <h4>Concepts needing attention</h4>
              {(detail.learning?.needsAttention || []).length === 0
                ? <p className="ops-muted">Nothing below 40% mastery.</p>
                : (
                  <ul className="ops-plain-list">
                    {detail.learning.needsAttention.map((c) => (
                      <li key={c.id}><strong>{c.name}</strong><span className="ops-muted">{c.mastery}% · {c.project}</span></li>
                    ))}
                  </ul>
                )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/* ================= SPACES & PROJECTS ================= */
function SpacesProjects({ spaces, projects }) {
  const [q, setQ] = useState('');
  const needle = q.trim().toLowerCase();
  const sp = (spaces || []).filter((s) => !needle || s.name.toLowerCase().includes(needle) || (s.owner || '').toLowerCase().includes(needle));
  const pr = (projects || []).filter((p) => !needle || p.name.toLowerCase().includes(needle) || (p.owner || '').toLowerCase().includes(needle) || (p.space || '').toLowerCase().includes(needle));
  return (
    <>
      <Card title="Spaces & projects" sub={`${(spaces || []).length} spaces · ${(projects || []).length} projects platform-wide`}
        actions={<input type="text" placeholder="Search spaces, projects, owners…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search spaces and projects" className="ops-search" />}>
        <h4 className="ops-subhead">Spaces</h4>
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead><tr>{['Space', 'Owner', 'Projects', 'Activity', 'Last activity'].map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {sp.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.name}</strong></td>
                  <td>{s.owner_name || s.owner || '—'}</td>
                  <td>{s.projects}</td>
                  <td>{s.activity}</td>
                  <td>{timeAgo(s.last_activity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {sp.length === 0 && <p className="ops-muted ops-pad">No spaces match.</p>}
        </div>
        <h4 className="ops-subhead">Projects</h4>
        <div className="ops-table-wrap">
          <table className="ops-table">
            <thead><tr>{['Project', 'Space', 'Owner', 'Progress', 'Activity', 'Last active'].map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>
              {pr.map((p) => (
                <tr key={p.id}>
                  <td><strong>{p.name}</strong></td>
                  <td>{p.space || '—'}</td>
                  <td>{p.owner_name || p.owner || '—'}</td>
                  <td className="ops-progress-cell"><ProgressBar value={p.progress} /><span>{p.progress}%</span></td>
                  <td>{(p.activity?.documents || 0) + (p.activity?.quizzes || 0) + (p.activity?.sessions || 0)}</td>
                  <td>{timeAgo(p.last_active)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pr.length === 0 && <p className="ops-muted ops-pad">No projects match.</p>}
        </div>
      </Card>
    </>
  );
}

/* ================= ACTIVITY ================= */
function ActivityList({ items, compact }) {
  if (!items || items.length === 0) return <p className="ops-muted">No activity recorded yet.</p>;
  return (
    <ul className={`ops-activity ${compact ? 'ops-activity-compact' : ''}`}>
      {(compact ? items.slice(0, 8) : items).map((e, i) => (
        <li key={`${e.id}-${i}`}>
          <StatusBadge tone="muted">{e.label || e.type}</StatusBadge>
          <div>
            <p>{e.text}</p>
            <small className="ops-muted">{[e.user, e.project].filter(Boolean).join(' · ')}{e.time ? ` · ${timeAgo(e.time)}` : ''}</small>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Activity({ data, onFilter }) {
  const [type, setType] = useState('');
  const [user, setUser] = useState('');
  const [days, setDays] = useState(30);
  useEffect(() => { onFilter({ days, limit: 50 }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const apply = () => onFilter({ type: type || undefined, user: user || undefined, days, limit: 50 });
  return (
    <Card title="Platform activity" sub="Every significant event, newest first"
      actions={
        <div className="ops-filters">
          <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter by activity type" className="ops-select">
            <option value="">All types</option>
            {(data?.types || []).map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input type="text" placeholder="Filter by user email…" value={user} onChange={(e) => setUser(e.target.value)} aria-label="Filter by user" className="ops-search" />
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label="Filter by time period" className="ops-select">
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button type="button" onClick={apply} className="ops-apply">Apply</button>
        </div>
      }>
      <ActivityList items={data?.items} />
    </Card>
  );
}

/* ================= AI USAGE ================= */
const fmtTokens = (v) => {
  const n = Number(v) || 0;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
};
const fmtCost = (v) => `$${(Number(v) || 0).toFixed(4)}`;
const fmtMs = (v) => (v == null ? '—' : `${Math.round(Number(v))}ms`);
// Friendly labels so the table never shows a blank/raw provider or feature.
// Backend now resolves legacy provider='none' to the configured provider;
// any remaining 'none' truly means "no LLM call" → show as system.
const FEATURE_LABELS = {
  tutor_answer: 'AI Tutor',
  quiz_generation: 'Quiz generation',
  quiz_evaluation: 'Quiz evaluation',
  assignment_generation: 'Assignment generation',
  assignment_evaluation: 'Assignment evaluation',
  concept_extraction: 'Concept extraction',
  recommendations: 'Recommendations',
  summarization: 'Summarization',
  other: 'Other',
};
const displayFeature = (f) => FEATURE_LABELS[f] || f || '—';
const displayProvider = (p) => {
  if (!p || p === '—') return '—';
  if (p === 'none') return 'system';
  return p;
};
const displayModel = (m) => {
  if (!m || m === '—' || m === 'unconfigured' || m === 'fake') return '—';
  return m;
};

function AiUsage({ usage, onFilter }) {
  const [feature, setFeature] = useState('');
  const [provider, setProvider] = useState('all');
  useEffect(() => { onFilter({}); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const apply = () => onFilter({
    ...(feature.trim() ? { feature: feature.trim() } : {}),
    ...(provider && provider !== 'all' ? { provider } : {}),
  });
  if (!usage) return <EmptyState title="No AI usage data" body="Usage appears once the platform serves AI requests." />;
  const groups = usage.groups || [];
  const providers = usage.providers || [];
  return (
    <div className="aiu-wrap">
      <div className="aiu-filters">
        <label className="aiu-filter">
          <span>Feature</span>
          <input
            type="text" placeholder="e.g. quiz_generation" value={feature}
            onChange={(e) => setFeature(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') apply(); }}
            aria-label="Filter by feature" className="aiu-input"
          />
        </label>
        <label className="aiu-filter">
          <span>Provider</span>
          <select value={provider} onChange={(e) => setProvider(e.target.value)} aria-label="Filter by provider" className="aiu-select">
            <option value="all">All</option>
            {providers.map((p) => <option key={p} value={p}>{displayProvider(p)}</option>)}
          </select>
        </label>
        <button type="button" onClick={apply} className="aiu-refresh">Refresh</button>
      </div>
      <div className="aiu-kpis">
        <div className="aiu-kpi"><span className="aiu-num">{usage.calls ?? usage.totals?.interactions ?? 0}</span><span className="aiu-label">Calls</span></div>
        <div className="aiu-kpi"><span className="aiu-num">{fmtTokens(usage.tokens)}</span><span className="aiu-label">Tokens</span></div>
        <div className="aiu-kpi"><span className="aiu-num">{fmtCost(usage.cost)}</span><span className="aiu-label">Cost</span></div>
        <div className="aiu-kpi"><span className="aiu-num">{usage.errorRate != null ? `${Number(usage.errorRate).toFixed(1)}%` : '—'}</span><span className="aiu-label">Error rate</span></div>
        <div className="aiu-kpi"><span className="aiu-num">{fmtMs(usage.latencyP50)}</span><span className="aiu-label">Latency p50</span></div>
        <div className="aiu-kpi"><span className="aiu-num">{fmtMs(usage.latencyP95)}</span><span className="aiu-label">Latency p95</span></div>
      </div>
      <section className="aiu-card">
        <h3 className="aiu-card-title">Feature × provider × model × day</h3>
        {groups.length === 0 ? (
          <p className="ops-muted ops-pad">{usage.message || 'No AI calls match these filters yet.'}</p>
        ) : (
          <div className="aiu-table-wrap">
            <table className="aiu-table">
              <thead>
                <tr>{['Day', 'Feature', 'Provider', 'Model', 'Calls', 'Tokens', 'Cost', 'Avg ms'].map((h) => <th key={h} className={['Calls', 'Tokens', 'Cost', 'Avg ms'].includes(h) ? 'aiu-r' : ''}>{h}</th>)}</tr>
              </thead>
              <tbody>
                {groups.map((g, i) => (
                  <tr key={`${g.day}-${g.feature}-${g.provider}-${g.model}-${i}`}>
                    <td className="aiu-mono">{g.day}</td>
                    <td title={g.feature}>{displayFeature(g.feature)}</td>
                    <td className="aiu-dim" title={g.provider === 'none' ? 'No LLM call (deterministic path)' : g.provider}>{displayProvider(g.provider)}</td>
                    <td className="aiu-dim">{displayModel(g.model)}</td>
                    <td className="aiu-r aiu-mono">{g.calls}</td>
                    <td className="aiu-r aiu-mono">{fmtTokens(g.tokens)}</td>
                    <td className="aiu-r aiu-mono">{fmtCost(g.cost)}</td>
                    <td className="aiu-r aiu-mono">{fmtMs(g.avgMs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

/* ================= AI EVALUATION ================= */
const fmtPct1 = (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`);
const fmtInt = (v) => (v == null ? '—' : `${Number(v).toLocaleString()}`);
const fmtAvg2 = (v) => (v == null ? '—' : Number(v).toFixed(2));
const mmdd = (iso) => {
  if (!iso) return '—';
  const parts = String(iso).split('-');
  if (parts.length < 3) return String(iso);
  return `${parts[1]}-${parts[2]}`;
};

function WeekChart({ points }) {
  const data = points || [];
  const w = 900;
  const h = 220;
  const padL = 8;
  const padR = 12;
  const padT = 12;
  const padB = 28;
  if (!data.length) {
    return (
      <div>
        <svg viewBox={`0 0 ${w} ${h}`} className="ops-spark" role="img" aria-label="Supported rate by week (no data)">
          {[0.2, 0.4, 0.6, 0.8].map((f, i) => (
            <line key={i} x1={padL + (w - padL - padR) * f} y1={padT} x2={padL + (w - padL - padR) * f} y2={h - padB}
              stroke="var(--border)" strokeWidth="1" strokeDasharray="4 4" />
          ))}
          <line x1={padL} y1={padT} x2={padL} y2={h - padB} stroke="var(--muted)" strokeWidth="1" />
          <line x1={padL} y1={h - padB} x2={w - padR} y2={h - padB} stroke="var(--muted)" strokeWidth="1" />
        </svg>
        <p className="ops-muted ops-pad">No weekly data in this range yet.</p>
      </div>
    );
  }
  const stepX = data.length > 1 ? (w - padL - padR) / (data.length - 1) : 0;
  const yFor = (rate) => {
    const r = Math.max(0, Math.min(100, Number(rate) || 0));
    return padT + (1 - r / 100) * (h - padT - padB);
  };
  const pts = data.map((p, i) => `${(padL + i * stepX).toFixed(1)},${yFor(p.rate).toFixed(1)}`).join(' ');
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="ops-spark" role="img" aria-label="Supported rate by week">
        {[0, 25, 50, 75, 100].map((gv) => (
          <line key={gv} x1={padL} y1={yFor(gv)} x2={w - padR} y2={yFor(gv)}
            stroke="var(--border)" strokeWidth="1" strokeDasharray={gv === 0 ? undefined : '4 4'} opacity="0.7" />
        ))}
        {data.length === 1 ? (
          <circle cx={padL} cy={yFor(data[0].rate)} r="4" fill="var(--primary)">
            <title>{`${data[0].week}: ${fmtPct1(data[0].rate)}`}</title>
          </circle>
        ) : (
          <>
            <polyline points={pts} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            {data.map((p, i) => (
              <circle key={p.week} cx={padL + i * stepX} cy={yFor(p.rate)} r="3.5" fill="var(--primary)">
                <title>{`${p.week}: ${fmtPct1(p.rate)} (${p.supported}/${p.answers})`}</title>
              </circle>
            ))}
          </>
        )}
        {data.map((p, i) => (
          <text key={`x-${p.week}`} x={padL + i * stepX} y={h - 8} textAnchor="middle" fontSize="11" fill="var(--muted)">
            {mmdd(p.week)}
          </text>
        ))}
      </svg>
    </div>
  );
}

function EvalKpi({ value, label, sub }) {
  return (
    <div className="aiu-kpi">
      <span className="aiu-num">{value}</span>
      <span className="aiu-label">{label}</span>
      {sub && <span className="ops-muted" style={{ fontSize: 12 }}>{sub}</span>}
    </div>
  );
}

function AiEvaluation({ evaluations, onFilter }) {
  const [days, setDays] = useState(30);
  useEffect(() => { onFilter({ days: 30 }); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (d) => { setDays(d); onFilter({ days: d }); };
  const refresh = () => onFilter({ days });

  if (!evaluations) {
    return <EmptyState title="Loading evaluation" body="Fetching tutor, retrieval, assessment and recommendation quality…" />;
  }
  const t = evaluations.tutor || {};
  const r = evaluations.retrieval || {};
  const a = evaluations.assessment || {};
  const rec = evaluations.recommendations || {};
  const byModel = r.byModel || [];
  const week = t.supportedByWeek || [];

  return (
    <div className="aiu-wrap">
      <div className="aiu-filters" role="group" aria-label="Evaluation time range">
        {[{ label: '7d', value: 7 }, { label: '30d', value: 30 }, { label: 'All', value: 0 }].map((o) => (
          <button
            key={o.label}
            type="button"
            onClick={() => pick(o.value)}
            className={`ops-tab ${days === o.value ? 'ops-tab-active' : ''}`}
            aria-pressed={days === o.value}
          >
            {o.label}
          </button>
        ))}
        <button type="button" onClick={refresh} className="ops-tab">Refresh</button>
      </div>

      {!evaluations.tracked && (
        <p className="ops-muted">
          No evaluation data in this range yet — quality signals will appear here once tutor answers,
          quizzes and recommendations are recorded. Nothing is fabricated in the meantime.
        </p>
      )}

      <span className="eval-label">Tutor quality</span>
      <div className="aiu-kpis">
        <EvalKpi value={fmtInt(t.answers)} label="Answers" />
        <EvalKpi value={fmtInt(t.supported)} label="Supported" />
        <EvalKpi value={fmtInt(t.unsupported)} label="Unsupported" />
        <EvalKpi value={fmtPct1(t.supportedRate)} label="Supported rate" />
        <EvalKpi value={fmtPct1(t.citationCoverage)} label="Citation coverage" />
        <EvalKpi value={fmtAvg2(t.avgCitations)} label="Avg citations" />
      </div>
      <section className="aiu-card">
        <h3 className="aiu-card-title">Supported rate by week (%)</h3>
        <WeekChart points={week} />
      </section>

      <span className="eval-label">Retrieval grounding</span>
      <div className="aiu-kpis aiu-kpis-2">
        <EvalKpi value={fmtInt(r.tutorCalls)} label="Tutor calls" />
        <EvalKpi value={fmtPct1(r.zeroContextRate)} label="Zero-context rate" />
      </div>
      <section className="aiu-card">
        <h3 className="aiu-card-title">Retrieval by model</h3>
        {byModel.length === 0 ? (
          <p className="ops-muted ops-pad">
            No tutor model usage in this range yet.
          </p>
        ) : (
          <div className="aiu-table-wrap">
            <table className="aiu-table">
              <thead>
                <tr><th>Model</th><th className="aiu-r">Calls</th><th className="aiu-r">Tokens</th><th className="aiu-r">Avg ms</th></tr>
              </thead>
              <tbody>
                {byModel.map((m) => (
                  <tr key={m.model}>
                    <td className="aiu-mono">{displayModel(m.model)}</td>
                    <td className="aiu-r aiu-mono">{fmtInt(m.calls)}</td>
                    <td className="aiu-r aiu-mono">{fmtTokens(m.tokens)}</td>
                    <td className="aiu-r aiu-mono">{fmtMs(m.avgMs)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <span className="eval-label">Assessment quality</span>
      <div className="aiu-kpis">
        <EvalKpi value={fmtInt(a.mcqAttempts)} label="MCQ attempts" />
        <EvalKpi value={fmtAvg2(a.mcqAvgScore)} label="MCQ avg score" />
        <EvalKpi value={fmtInt(a.openEndedGrades)} label="Open-ended grades" />
        <EvalKpi value={fmtAvg2(a.openEndedAvg)} label="Open-ended avg" />
        <EvalKpi value={fmtInt(a.verdictPass)} label="Verdict pass" />
        <EvalKpi value={fmtInt(a.verdictFail)} label="Verdict fail" sub={a.verdictPartial != null ? `Partial: ${fmtInt(a.verdictPartial)}` : null} />
      </div>
      <span className="eval-label">Recommendations</span>
      <div className="aiu-kpis aiu-kpis-2">
        <EvalKpi value={fmtInt(rec.total)} label="Total generated" />
      </div>
      {rec.message && <p className="ops-muted">{rec.message}</p>}
    </div>
  );
}

/* ================= PROCESSING ================= */
function Processing({ summary, jobs }) {
  const s = summary || { queued: 0, processing: 0, completed: 0, failed: 0 };
  return (
    <>
      <div className="ops-kpis">
        <Kpi icon={I.doc} value={s.queued} label="Queued" />
        <Kpi icon={I.pulse} value={s.processing} label="Processing" />
        <Kpi icon={I.quiz} value={s.completed} label="Completed" />
        <Kpi icon={I.cpu} value={s.failed} label="Failed" />
      </div>
      <Card title="Recent background work" sub="Document ingestion, quiz generation and assignments — terminal states marked">
        {(jobs || []).length === 0 && <p className="ops-muted">No background work recorded.</p>}
        {(jobs || []).map((j) => (
          <div key={`${j.type}-${j.id}`} className="ops-job-row">
            <HealthDot status={j.terminal ? (j.status === 'failed' ? 'unavailable' : 'healthy') : 'degraded'} />
            <div>
              <strong>{j.name}</strong>
              <small className="ops-muted">{j.type} · {j.user || 'unknown'} · {j.started ? timeAgo(j.started) : ''}</small>
            </div>
            <StatusBadge status={j.status} />
          </div>
        ))}
      </Card>
    </>
  );
}

/* ================= HEALTH ================= */
function Health({ health }) {
  if (!health) return <EmptyState title="Health unavailable" body="Could not reach the health endpoint." />;
  return (
    <Card title="System health" sub="Application-level view — not infrastructure monitoring">
      <ul className="ops-health-list ops-health-big">
        {(health.components || []).map((c) => (
          <li key={c.name}>
            <HealthDot status={c.status} />
            <span className="ops-health-name">{c.name}</span>
            <span className={`ops-health-status ${HEALTH_TONE[c.status] || ''}`}>{c.status}</span>
            {c.detail && <span className="ops-health-detail">{c.detail}</span>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* ================= SHELL ================= */
export default function Admin() {
  const dispatch = useDispatch();
  const { admin } = useSelector((s) => s.analytics);
  const [tab, setTab] = useState('Overview');
  const [openUserId, setOpenUserId] = useState(null);

  useEffect(() => {
    dispatch(loadAdminOverview());
    dispatch(loadAdminUsers());
    dispatch(loadAdminSpaces());
    dispatch(loadAdminProjects());
    dispatch(loadAdminActivity({ days: 30, limit: 50 }));
    dispatch(loadAdminJobs());
    dispatch(loadAdminEvaluations({ days: 30 }));
    dispatch(loadAdminUsage());
    dispatch(loadAdminHealth());
  }, [dispatch]);

  const openUser = (id) => {
    setOpenUserId(id);
    dispatch(loadAdminUserDetail(id));
  };

  const detail = useMemo(
    () => (admin.userDetail && openUserId && String(admin.userDetail.id) === String(openUserId) ? admin.userDetail : null),
    [admin.userDetail, openUserId],
  );

  return (
    <motion.div
      className="ops-wrap"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <PageHeader
        eyebrow="AI Learning Operations Center"
        title="Admin Dashboard"
        sub="Users → learning activity → AI usage → AI quality → processing → system health."
        actions={<StatusBadge tone="danger">Admin Only</StatusBadge>}
      />
      <div className="ops-tabs" role="tablist" aria-label="Admin sections">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={`ops-tab ${tab === t ? 'ops-tab-active' : ''}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'Overview' && <Overview ov={admin.overview} />}
      {tab === 'Users' && (
        <Users users={admin.users} onOpen={openUser} detail={detail} onClose={() => setOpenUserId(null)} />
      )}
      {tab === 'Spaces & Projects' && <SpacesProjects spaces={admin.spaces} projects={admin.projects} />}
      {tab === 'Activity' && (
        <Activity data={admin.activity} onFilter={(p) => dispatch(loadAdminActivity(p))} />
      )}
      {tab === 'AI Usage' && (
        <AiUsage usage={admin.usage} onFilter={(p) => dispatch(loadAdminUsage(p))} />
      )}
      {tab === 'AI Evaluation' && (
        <AiEvaluation evaluations={admin.evaluations} onFilter={(p) => dispatch(loadAdminEvaluations(p))} />
      )}
      {tab === 'Processing' && <Processing summary={admin.jobSummary} jobs={admin.jobs} />}
      {tab === 'Health' && <Health health={admin.health} />}
    </motion.div>
  );
}
