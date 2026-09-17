import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion } from 'framer-motion';
import { loadProjectAnalytics, clearProjectAnalytics } from '../../../../features/analytics/analyticsSlice.js';
import { PageHeader, Stat, StatusBadge, EmptyState } from '../../../../components/ui/ui.jsx';
import './Analytics.css';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'mastery', label: 'Mastery' },
  { id: 'quizzes', label: 'Quizzes' },
  { id: 'tutor', label: 'Tutor' },
];

const RANGES = [
  { id: 7, label: '7D' },
  { id: 30, label: '30D' },
  { id: 90, label: '90D' },
  { id: 0, label: 'All' },
];

const TREND_META = {
  improving: { label: 'Improving ↑', tone: 'success' },
  stable: { label: 'Stable →', tone: 'muted' },
  attention: { label: 'Attention ↓', tone: 'danger' },
  insufficient: { label: 'Pending', tone: 'muted' },
};

function GrowthChart({ series }) {
  const W = 560, H = 220, PAD = 34;
  if (!series || series.length === 0) {
    return (
      <EmptyState
        title="No growth data yet"
        body="Complete a few assessments to see your growth over time."
      />
    );
  }
  const single = series.length === 1;
  const xs = single
    ? [W / 2]
    : series.map((_, i) => PAD + (i * (W - PAD * 2)) / Math.max(1, series.length - 1));
  const ys = series.map((p) => H - PAD - (Math.min(100, Math.max(0, p.mastery)) / 100) * (H - PAD * 2));
  const line = xs.map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(' ');
  const first = series[0].date, last = series[series.length - 1].date;
  return (
    <div className="growth-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Mastery over time, from ${series[0].mastery}% on ${first} to ${series[series.length - 1].mastery}% on ${last}.`}>
        {[0, 25, 50, 75, 100].map((v) => {
          const y = H - PAD - (v / 100) * (H - PAD * 2);
          return (
            <g key={v}>
              <line x1={PAD} y1={y} x2={W - PAD} y2={y} className="grid-line" />
              <text x={PAD - 6} y={y + 4} textAnchor="end" className="axis-label">{v}%</text>
            </g>
          );
        })}
        <path d={line} className="growth-line" />
        {xs.map((x, i) => (
          <circle key={i} cx={x} cy={ys[i]} r="3.5" className="growth-dot">
            <title>{`${series[i].date}: ${series[i].mastery}%`}</title>
          </circle>
        ))}
        <text x={PAD} y={H - 8} className="axis-label">{first}</text>
        <text x={W - PAD} y={H - 8} textAnchor="end" className="axis-label">{last}</text>
      </svg>
      {single && <p className="text-[13px] text-muted">Only one measurement so far — complete another assessment to draw the trend line.</p>}
    </div>
  );
}

function BarRow({ label, value, color }) {
  return (
    <div className="flex items-center gap-2.5 text-xs">
      <span className="w-[88px] shrink-0 truncate text-muted">{label}</span>
      <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
        <div className="h-full rounded-full" style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }} />
      </div>
      <span className="w-11 shrink-0 text-right font-semibold text-heading">{value}%</span>
    </div>
  );
}

function Card({ children, className }) {
  return (
    <div className={`flex min-w-0 flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm ${className || ''}`}>
      {children}
    </div>
  );
}

function FilterPills({ options, value, onChange, label, small }) {
  return (
    <div className="flex flex-wrap gap-1.5" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="tab"
          aria-selected={value === o.id}
          onClick={() => onChange(o.id)}
          className={`rounded-full font-medium transition-colors ${
            small ? 'px-2.5 py-1 text-xs' : 'px-3.5 py-1.5 text-[13px]'
          } border ${
            value === o.id
              ? 'border-primary bg-primary font-semibold text-white'
              : 'border-line bg-surface text-muted hover:bg-canvas hover:text-ink'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

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

export default function Analytics({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { project, status, error } = useSelector((s) => s.analytics);
  const [filter, setFilter] = useState('all');
  const [range, setRange] = useState(0);
  const [perfDate, setPerfDate] = useState('all');
  const [showAllGrowth, setShowAllGrowth] = useState(false);

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadProjectAnalytics({ spaceId, projectId }));
    return () => { dispatch(clearProjectAnalytics()); };
  }, [dispatch, spaceId, projectId]);

  if (status === 'loading' && !project) return <p className="text-sm text-muted">Loading analytics...</p>;
  if (error && !project) return <div className="error-banner">{error}</div>;
  if (!project) {
    return (
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <EmptyState title="Learning Analytics" body="Complete a quiz to unlock your insights." />
      </motion.div>
    );
  }

  const show = (section) => filter === 'all' || filter === section;
  const growth = project.growth || { overall: {}, concepts: [], series: [] };
  const overall = growth.overall || {};
  const overallMeta = TREND_META[overall.trend] || TREND_META.insufficient;
  const baseSeries = (growth.series && growth.series.length > 0)
    ? growth.series
    : (((project.concepts || []).length > 0)
      ? [{ date: new Date().toISOString().slice(0, 10), mastery: (project.kpis && project.kpis.averageMastery) || 0 }]
      : []);
  const rangedSeries = (() => {
    const series = baseSeries;
    if (!range || series.length === 0) return series;
    const maxDate = series[series.length - 1].date;
    const cutoff = new Date(maxDate);
    cutoff.setDate(cutoff.getDate() - range);
    return series.filter((p) => new Date(p.date) >= cutoff);
  })();
  const fmtGrowth = (g) => (g == null ? '—' : `${g > 0 ? '+' : ''}${g} pts`);
  const dist = project.distribution || { strong: 0, learning: 0, needsWork: 0 };
  const distTotal = (dist.strong || 0) + (dist.learning || 0) + (dist.needsWork || 0);
  const pct = (n) => (distTotal ? Math.round((n / distTotal) * 100) : 0);
  const overallMastery = overall.current != null ? overall.current : (project.kpis.averageMastery || 0);
  const quizTrend = (project.quizzes && project.quizzes.trend) || [];
  const assignTrend = (project.assignments && project.assignments.trend) || [];
  const perfDates = [...new Set([...quizTrend, ...assignTrend].map((t) => t.date).filter(Boolean))].sort();
  const quizDaily = avgByDate(quizTrend);
  const assignDaily = avgByDate(assignTrend);
  const perfQuizDetail = quizTrend.filter((t) => t.date === perfDate);
  const perfAssignDetail = assignTrend.filter((t) => t.date === perfDate);
  const sortedGrowth = [...(growth.concepts || [])].sort((a, b) => {
    const ad = a.growth == null ? 1 : 0, bd = b.growth == null ? 1 : 0;
    if (ad !== bd) return ad - bd;
    return (b.current || 0) - (a.current || 0);
  });
  const growthWithData = (growth.concepts || []).filter((c) => c.growth != null).length;
  const visibleGrowth = showAllGrowth ? sortedGrowth : sortedGrowth.slice(0, 8);

  return (
    <div className="flex flex-col gap-4">
      <PageHeader eyebrow="Analytics" title="Project Analytics" sub="Mastery, growth, and activity for this project." />
      <FilterPills options={FILTERS} value={filter} onChange={setFilter} label="Analytics sections" />

      {show('mastery') && (project.recommendations || []).length > 0 && (
        <Card className="border-l-2 border-l-primary">
          <h3 className="font-display text-sm font-semibold text-heading">Recommended Next Actions</h3>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {(project.recommendations || []).map((r, i) => (
              <div key={i} className="rounded-md bg-canvas px-3.5 py-3">
                <strong className="text-sm text-ink">{r.title}</strong>
                <p className="mt-0.5 text-[13px] text-muted">{r.text}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {show('mastery') && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat value={`${project.kpis.averageMastery}%`} label="Average Mastery" />
          <Stat value={`${project.kpis.quizAccuracy}%`} label="Quiz Accuracy" />
          <Stat value={project.kpis.quizzesCompleted} label="Quizzes Completed" />
          <Stat value={project.kpis.tutorMessages} label="Tutor Messages" />
        </div>
      )}

      {show('mastery') && (
        <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-5">
          <Card className="xl:col-span-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-sm font-semibold text-heading">Overall Growth Chart</h3>
                <p className="text-[13px] text-muted">Project average mastery over time.</p>
              </div>
              <FilterPills options={RANGES} value={range} onChange={setRange} label="Chart time range" small />
            </div>
            <GrowthChart series={rangedSeries} />
          </Card>
          <Card className="xl:col-span-2">
            <h3 className="font-display text-sm font-semibold text-heading">Overall Mastery</h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col gap-0.5">
                <span className="truncate font-display text-xl font-bold text-heading">{overallMastery}%</span>
                <span className="text-xs font-medium text-muted">Mastery</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className={`truncate font-display text-xl font-bold ${(overall.growth || 0) >= 0 ? 'text-accent' : 'text-danger'}`}>{fmtGrowth(overall.growth)}</span>
                <span className="text-xs font-medium text-muted">Growth</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span>{overall.trend === 'insufficient' ? (
                  <span className="font-display text-xl font-bold text-heading">—</span>
                ) : (
                  <StatusBadge tone={overallMeta.tone}>{overallMeta.label}</StatusBadge>
                )}</span>
                <span className="text-xs font-medium text-muted">Trend</span>
              </div>
            </div>
            <p className="text-[13px] text-muted">{overall.insight || 'Complete assessments to start measuring growth.'}</p>
          </Card>
        </div>
      )}

      {show('mastery') && (growth.concepts || []).length > 0 && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-display text-sm font-semibold text-heading">Concept Growth</h3>
              <p className="text-[13px] text-muted">{growthWithData} of {growth.concepts.length} concepts have measured growth.</p>
            </div>
            {sortedGrowth.length > 8 && (
              <button
                type="button"
                onClick={() => setShowAllGrowth((v) => !v)}
                className="rounded px-1 py-0.5 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary"
              >
                {showAllGrowth ? 'Show less' : `Show all (${sortedGrowth.length})`}
              </button>
            )}
          </div>
          <div className="overflow-x-auto">
            <div className="flex min-w-[560px] flex-col gap-2">
              {visibleGrowth.map((c) => {
                const meta = TREND_META[c.trend] || TREND_META.insufficient;
                return (
                  <div key={c.concept_id} className="flex items-center gap-2.5 text-xs" title={c.insight}>
                    <span className="w-32 shrink-0 truncate text-ink">{c.name}</span>
                    <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${c.current}%` }} />
                    </div>
                    <span className="w-11 shrink-0 text-right font-semibold text-heading">{c.current}%</span>
                    <span className={`w-14 shrink-0 text-right font-semibold ${(c.growth || 0) >= 0 ? 'text-accent' : 'text-danger'}`}>{fmtGrowth(c.growth)}</span>
                    <span className="w-[118px] shrink-0 text-right">
                      {c.trend === 'insufficient' ? (
                        <span className="font-semibold text-muted">—</span>
                      ) : (
                        <StatusBadge tone={meta.tone}>{meta.label}</StatusBadge>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>
      )}

      {show('quizzes') && (
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-display text-sm font-semibold text-heading">Quiz & Assignment Performance</h3>
              <p className="text-[13px] text-muted">Scores grouped by date.</p>
            </div>
            <select
              value={perfDate}
              onChange={(e) => setPerfDate(e.target.value)}
              aria-label="Filter performance by date"
              className="min-h-9 rounded-md border border-line bg-surface px-3 text-sm"
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
              {perfQuizDetail.length > 0 && (
                <>
                  <h4 className="mt-1 text-xs font-bold uppercase tracking-wide text-muted">Quizzes · {perfDate}</h4>
                  {perfQuizDetail.map((t, i) => (
                    <BarRow key={t.id || `q-${t.date}-${i}`} label={t.name || t.date} value={t.score} color={scoreColor(t.score)} />
                  ))}
                </>
              )}
              {perfAssignDetail.length > 0 && (
                <>
                  <h4 className="mt-1 text-xs font-bold uppercase tracking-wide text-muted">Assignments · {perfDate}</h4>
                  {perfAssignDetail.map((t, i) => (
                    <BarRow key={t.id || `a-${t.date}-${i}`} label={t.name || t.date} value={t.score} color={scoreColor(t.score)} />
                  ))}
                </>
              )}
            </>
          )}
        </Card>
      )}

      {show('mastery') && (
        <Card>
          <h3 className="font-display text-sm font-semibold text-heading">Concept Mastery Distribution</h3>
          {distTotal === 0 && <p className="text-[13px] text-muted">No concepts yet. Upload a PDF in Materials.</p>}
          {distTotal > 0 && (
            <>
              <div className="flex flex-wrap gap-4 text-xs text-muted">
                <span className="inline-flex items-center gap-1.5"><i className="dot-s strong" /> Strong {dist.strong}</span>
                <span className="inline-flex items-center gap-1.5"><i className="dot-s learning" /> Learning {dist.learning}</span>
                <span className="inline-flex items-center gap-1.5"><i className="dot-s weak" /> Needs work {dist.needsWork}</span>
              </div>
              <div className="stacked-bar">
                <div style={{ width: `${pct(dist.strong)}%` }} className="seg strong" />
                <div style={{ width: `${pct(dist.learning)}%` }} className="seg learning" />
                <div style={{ width: `${pct(dist.needsWork)}%` }} className="seg weak" />
              </div>
            </>
          )}
        </Card>
      )}

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        {show('mastery') && (
          <Card>
            <h3 className="font-display text-sm font-semibold text-heading">Needs Attention</h3>
            {(project.needsAttention || []).length === 0 && <p className="text-[13px] text-muted">Nothing needs attention right now.</p>}
            {(project.needsAttention || []).map((c) => (
              <div key={c.id} className="flex items-center gap-2.5 text-xs">
                <span className="w-32 shrink-0 truncate text-ink">{c.name}</span>
                <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
                  <div className="h-full rounded-full bg-danger" style={{ width: `${c.mastery}%` }} />
                </div>
                <StatusBadge tone="danger">{c.mastery}%</StatusBadge>
              </div>
            ))}
          </Card>
        )}
        {show('tutor') && (
          <Card>
            <h3 className="font-display text-sm font-semibold text-heading">AI Tutor Activity</h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="flex flex-col gap-0.5">
                <span className="font-display text-xl font-bold text-heading">{project.tutor.total}</span>
                <span className="text-xs font-medium text-muted">Messages</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="font-display text-xl font-bold text-heading">{project.tutor.user}</span>
                <span className="text-xs font-medium text-muted">You asked</span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="font-display text-xl font-bold text-heading">{project.tutor.assistant}</span>
                <span className="text-xs font-medium text-muted">Tutor answered</span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
