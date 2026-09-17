import { useState } from 'react';
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion } from 'framer-motion';
import { loadOverview } from '../../features/analytics/analyticsSlice.js';
import { PageHeader, Stat, StatusBadge } from '../../components/ui/ui.jsx';

function avgByDate(items) {
  const map = {};
  (items || []).forEach((t) => {
    if (!t || !t.date || !Number.isFinite(Number(t.score))) return;
    const e = (map[t.date] = map[t.date] || { total: 0, count: 0 });
    e.total += Number(t.score);
    e.count += 1;
  });
  return Object.entries(map)
    .map(([date, v]) => ({ date, score: Math.round((v.total / v.count) * 10) / 10, count: v.count }))
    .sort((a, b) => (a.date < b.date ? -1 : 1));
}

function scoreColor(score) {
  return score >= 70 ? '#047857' : score >= 40 ? '#b45309' : '#b91c1c';
}

function detailLabel(t) {
  return [t.name, t.project, t.date].filter(Boolean).join(' · ');
}

function BarRow({ label, value, color }) {
  return (
    <div className="flex items-center gap-2.5 text-xs">
      <span className="w-[88px] shrink-0 truncate text-muted">{label}</span>
      <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
        <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="w-11 shrink-0 text-right font-semibold text-heading">{value}%</span>
    </div>
  );
}

function Card({ children }) {
  return (
    <div className="flex min-w-0 flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm">
      {children}
    </div>
  );
}

function CardTitle({ children }) {
  return <h3 className="font-display text-sm font-semibold text-heading">{children}</h3>;
}

function ConceptRow({ name, sub, value, barClass, badge }) {
  return (
    <div className="flex items-center gap-2.5 text-[13px]">
      <span className="min-w-0 flex-1 truncate font-medium text-ink">
        {name} {sub && <span className="text-muted">· {sub}</span>}
      </span>
      <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
        <div className={`h-full rounded-full ${barClass}`} style={{ width: `${value}%` }} />
      </div>
      {badge}
    </div>
  );
}

export default function GlobalAnalytics() {
  const dispatch = useDispatch();
  const { overview, status, error } = useSelector((s) => s.analytics);
  const [perfDate, setPerfDate] = useState('all');

  useEffect(() => { dispatch(loadOverview()); }, [dispatch]);

  if (status === 'loading' && !overview) {
    return (
      <div className="mx-auto w-full max-w-[1200px] px-6 py-8">
        <p className="text-sm text-muted">Loading analytics...</p>
      </div>
    );
  }
  if (error && !overview) {
    return (
      <div className="mx-auto w-full max-w-[1200px] px-6 py-8">
        <div className="error-banner">{error}</div>
      </div>
    );
  }
  if (!overview) return null;

  const { kpis, concepts, quizzes, tutor, activity } = overview;
  const quizTrend = (quizzes && quizzes.trend) || [];
  const assignTrend = (overview.assignments && overview.assignments.trend) || [];
  const perfDates = [...new Set([...quizTrend, ...assignTrend].map((t) => t.date).filter(Boolean))].sort();
  const quizDaily = avgByDate(quizTrend);
  const assignDaily = avgByDate(assignTrend);
  const masteryByProject = Object.values(overview.masteryByProject || {});
  const weakCount = (concepts.distribution && concepts.distribution.needsWork) || 0;
  const trendMeta = (t) => ({
    improving: { label: 'Improving ↑', tone: 'success' },
    stable: { label: 'Stable →', tone: 'muted' },
    attention: { label: 'Attention ↓', tone: 'danger' },
  }[t] || null);
  const fmtGrowth = (g) => (g == null ? '—' : `${g > 0 ? '+' : ''}${g} pts`);

  return (
    <motion.div
      className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-6 py-8 max-sm:px-4 max-sm:py-5"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <PageHeader
        eyebrow="Analytics"
        title="Analytics"
        sub="Progress across all your spaces, computed from your real activity."
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat value={`${kpis.averageMastery}%`} label="Average Mastery" />
        <Stat value={weakCount} label="Weak Concepts" />
        <Stat value={`${kpis.quizAccuracy}%`} label="Quiz Accuracy" />
        <Stat value={kpis.tutorMessages} label="Tutor Messages" />
      </div>

      <Card>
        <CardTitle>Mastery & Growth by Project</CardTitle>
        {masteryByProject.length === 0 && <p className="text-[13px] text-muted">No projects yet. Create one in Spaces.</p>}
        <div className="overflow-x-auto">
          <div className="flex min-w-[560px] flex-col gap-2">
            {masteryByProject.map((p) => {
              const meta = trendMeta(p.trend);
              return (
                <div key={p.project_id} className="flex items-center gap-2.5 text-xs">
                  <span className="w-32 shrink-0 truncate text-ink">{p.project_name}</span>
                  <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
                    <div className="h-full rounded-full bg-primary" style={{ width: `${p.average}%` }} />
                  </div>
                  <span className="w-11 shrink-0 text-right font-semibold text-heading">{p.average}%</span>
                  <span className={`w-14 shrink-0 text-right font-semibold ${(p.growth || 0) >= 0 ? 'text-accent' : 'text-danger'}`}>{fmtGrowth(p.growth)}</span>
                  <span className="w-[118px] shrink-0 text-right">
                    {meta ? <StatusBadge tone={meta.tone}>{meta.label}</StatusBadge> : <span className="font-semibold text-muted">—</span>}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Masonry flow: the four cards below have very uneven heights (an empty
          "Strongest Concepts" is ~70px tall). A strict 2-col grid would leave
          a dead void under the short card; columns let cards pack naturally. */}
      <div className="columns-1 gap-4 lg:columns-2 [&>*]:mb-4 [&>*]:break-inside-avoid">
        <Card>
          <CardTitle>Weakest Concepts</CardTitle>
          {(concepts.needsAttention || []).length === 0 && <p className="text-[13px] text-muted">Nothing needs attention right now.</p>}
          {(concepts.needsAttention || []).map((c) => (
            <ConceptRow
              key={c.id}
              name={c.name}
              sub={c.project_name}
              value={c.mastery}
              barClass="bg-danger"
              badge={<StatusBadge tone="danger">{c.mastery}%</StatusBadge>}
            />
          ))}
        </Card>
        <Card>
          <CardTitle>Strongest Concepts</CardTitle>
          {(concepts.strongest || []).length === 0 && <p className="text-[13px] text-muted">Score 70%+ on a concept to see it here.</p>}
          {(concepts.strongest || []).map((c) => (
            <ConceptRow
              key={c.id}
              name={c.name}
              sub={c.project_name}
              value={c.mastery}
              barClass="bg-accent"
              badge={<StatusBadge tone="success">{c.mastery}%</StatusBadge>}
            />
          ))}
        </Card>
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Quiz & Assignment Performance</CardTitle>
              <p className="text-[13px] text-muted">Scores grouped by date.</p>
            </div>
            <select
              value={perfDate}
              onChange={(e) => setPerfDate(e.target.value)}
              aria-label="Filter performance by date"
              className="min-h-9 rounded-md border border-line bg-surface px-2.5 text-xs font-semibold text-ink"
            >
              <option value="all">All dates</option>
              {perfDates.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
          </div>
          {quizTrend.length === 0 && assignTrend.length === 0 && (
            <p className="text-[13px] text-muted">No completed quizzes or assignments yet.</p>
          )}
          {perfDate === 'all' ? (
            <>
              {quizDaily.length > 0 && (
                <>
                  <h4 className="mt-1 text-xs font-bold uppercase tracking-wide text-muted">Quizzes</h4>
                  {quizDaily.map((t) => (
                    <BarRow key={`q-${t.date}`} label={`${t.date} · ${t.count} quiz${t.count === 1 ? '' : 'zes'}`} value={t.score} color={scoreColor(t.score)} />
                  ))}
                </>
              )}
              {assignDaily.length > 0 && (
                <>
                  <h4 className="mt-1 text-xs font-bold uppercase tracking-wide text-muted">Assignments</h4>
                  {assignDaily.map((t) => (
                    <BarRow key={`a-${t.date}`} label={`${t.date} · ${t.count} assignment${t.count === 1 ? '' : 's'}`} value={t.score} color={scoreColor(t.score)} />
                  ))}
                </>
              )}
            </>
          ) : (
            <>
              {quizTrend.filter((t) => t.date === perfDate).map((t, i) => (
                <BarRow key={`q-${t.date}-${i}`} label={detailLabel(t)} value={t.score} color={scoreColor(t.score)} />
              ))}
              {assignTrend.filter((t) => t.date === perfDate).map((t, i) => (
                <BarRow key={`a-${t.date}-${i}`} label={detailLabel(t)} value={t.score} color={scoreColor(t.score)} />
              ))}
            </>
          )}
        </Card>
        <Card>
          <CardTitle>Recent Activity</CardTitle>
          {(activity || []).length === 0 && <p className="text-[13px] text-muted">No activity yet.</p>}
          {(activity || []).slice(0, 5).map((a) => (
            <div key={`${a.type}-${a.id}`} className="flex items-start gap-2.5 border-b border-line py-2 first:pt-0 last:border-b-0 last:pb-0">
              <span className={`mt-[5px] h-2 w-2 shrink-0 rounded-full ${a.type === 'quiz' ? 'bg-primary' : a.type === 'assignment' ? 'bg-warning' : a.type === 'upload' ? 'bg-accent' : a.type === 'tutor' ? 'bg-info' : 'bg-primary'}`} />
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="truncate text-[13px] text-ink">{a.text}</span>
                <span className="text-[11px] text-muted">{a.project}{a.time ? ` · ${new Date(a.time).toLocaleDateString()}` : ''}</span>
              </div>
            </div>
          ))}
          <p className="text-xs text-muted">{tutor.total} tutor messages overall.</p>
        </Card>
      </div>
    </motion.div>
  );
}
