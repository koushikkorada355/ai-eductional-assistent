import { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { loadOverview } from '../../features/analytics/analyticsSlice.js';
import { PageHeader, Stat, StatusBadge, EmptyState, ProgressBar } from '../../components/ui/ui.jsx';
import { tabHref } from '../ProjectWorkspace/tabs.js';
import './Home.css';

/* Home dashboard (PDF §16): answers "Where was I, how am I doing, and what
 * should I do next?" — Continue Learning, Recent Projects, Overall
 * progress, Areas requiring attention, Recommended next action. All data
 * comes from GET /analytics/overview; nothing is fabricated. */

const projBase = (spaceId, projectId) => `/spaces/${spaceId}/projects/${projectId}`;

function ContinueCard({ quiz, project, navigate }) {
  let title = 'Start learning';
  let text = 'Create a space and project, upload a PDF, and start asking your tutor.';
  let cta = 'Go to Spaces';
  let href = '/spaces';
  let badge = null;
  if (quiz) {
    const active = quiz.status !== 'completed' && quiz.status !== 'failed';
    title = active ? `Resume: ${quiz.name}` : `Review: ${quiz.name}`;
    text = active
      ? `Quiz is ${quiz.status.replace('_', ' ')} in ${quiz.project_name || 'your project'}.`
      : `You scored ${quiz.average ?? '—'}% on this quiz.`;
    cta = active ? 'Resume quiz' : 'Review results';
    href = `${projBase(quiz.space_id, quiz.project_id)}?tab=quiz`;
    badge = <StatusBadge status={quiz.status}>{quiz.status.replace('_', ' ')}</StatusBadge>;
  } else if (project) {
    title = `Continue: ${project.name}`;
    text = `Pick up in ${project.spaceName || 'your space'} — ask the tutor or take a quiz.`;
    cta = 'Open project';
    href = tabHref('AI Tutor', project.spaceId, project.id);
  }
  return (
    <motion.section
      className="home-hero"
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div>
        <p className="home-eyebrow">Continue learning</p>
        <h3 className="home-hero-title">{title}</h3>
        <p className="home-muted">{text}</p>
        <div className="home-hero-row">
          <button type="button" onClick={() => navigate(href)} className="home-cta">
            {cta} →
          </button>
          {badge}
        </div>
      </div>
    </motion.section>
  );
}

/* Learning loop (PDF §1/§19): Spaces → Projects → Materials → Tutor →
 * Quiz → Mastery → Growth → Recommendations, each stage live from the
 * overview payload. Done stages are filled; untouched stages are hollow.
 * The ↻ badge closes the loop back into Continue Learning. */
function LearningLoop({ ov, newestProject, navigate }) {
  const kpis = ov?.kpis || {};
  const avgMastery = ov?.concepts?.average ?? 0;
  const improving = Object.values(ov?.masteryByProject || {})
    .filter((m) => m?.trend === 'improving').length;
  const recCount = (ov?.recommendations || []).length;
  const p = newestProject || null;
  const ptab = (t) => (p ? `${projBase(p.spaceId, p.id)}?tab=${t}` : '/spaces');
  const stages = [
    { label: 'Spaces', value: `${kpis.spaces ?? 0}`, done: (kpis.spaces ?? 0) > 0, href: '/spaces' },
    { label: 'Projects', value: `${kpis.projects ?? 0}`, done: (kpis.projects ?? 0) > 0, href: '/spaces' },
    { label: 'Materials', value: `${kpis.documents ?? 0}`, done: (kpis.documents ?? 0) > 0, href: ptab('materials') },
    { label: 'Tutor', value: `${kpis.tutorMessages ?? 0}`, done: (kpis.tutorMessages ?? 0) > 0, href: p ? tabHref('AI Tutor', p.spaceId, p.id) : null },
    { label: 'Quiz', value: `${kpis.quizzesCompleted ?? 0}`, done: (kpis.quizzesCompleted ?? 0) > 0, href: ptab('quiz') },
    { label: 'Mastery', value: `${avgMastery}%`, done: avgMastery >= 40, href: ptab('concepts') },
    { label: 'Growth', value: improving > 0 ? `${improving} ↑` : '—', done: improving > 0, href: ptab('analytics') },
    { label: 'Recommendations', value: `${recCount}`, done: recCount > 0, href: null },
  ];
  return (
    <section className="home-card home-loop" aria-label="Your learning loop">
      <p className="home-eyebrow">Your learning loop</p>
      <div className="home-loop-track">
        {stages.map((s, i) => (
          <div key={s.label} className="home-loop-step">
            {s.href ? (
              <button type="button" onClick={() => navigate(s.href)} className="home-loop-node" aria-label={`${s.label}: ${s.value}`}>
                <span className={`home-loop-dot ${s.done ? 'done' : 'todo'}`} aria-hidden="true">
                  {s.done ? '✓' : (i + 1)}
                </span>
                <span className="home-loop-label">{s.label}</span>
                <span className="home-loop-value">{s.value}</span>
              </button>
            ) : (
              <div className="home-loop-node" aria-label={`${s.label}: ${s.value}`}>
                <span className={`home-loop-dot ${s.done ? 'done' : 'todo'}`} aria-hidden="true">
                  {s.done ? '✓' : (i + 1)}
                </span>
                <span className="home-loop-label">{s.label}</span>
                <span className="home-loop-value">{s.value}</span>
              </div>
            )}
            {i < stages.length - 1 && <span className="home-loop-connector" aria-hidden="true" />}
          </div>
        ))}
        <span className="home-loop-restart" title="The loop continues — recommendations feed back into learning">↻</span>
      </div>
    </section>
  );
}

export default function Home() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { overview: ov, status, error } = useSelector((s) => s.analytics);

  useEffect(() => { dispatch(loadOverview()); }, [dispatch]);

  const projects = useMemo(() => {
    const out = [];
    for (const s of ov?.spaces || []) {
      for (const p of s.projects || []) {
        out.push({ ...p, spaceId: s.id, spaceName: s.name });
      }
    }
    return out;
  }, [ov]);

  if (status === 'loading' && !ov) {
    return (
      <div className="home-wrap">
        <PageHeader eyebrow="Home" title="Welcome back" sub="Loading your learning snapshot…" />
        <p className="home-muted">Loading…</p>
      </div>
    );
  }
  if (error && !ov) {
    return (
      <div className="home-wrap">
        <PageHeader eyebrow="Home" title="Welcome back" sub="Where you left off, how you're doing, and what to do next." />
        <EmptyState title="Couldn't load your dashboard" body={error} />
      </div>
    );
  }

  const kpis = ov?.kpis || {};
  const concepts = ov?.concepts || {};
  const needsAttention = concepts.needsAttention || [];
  const recommendations = ov?.recommendations || [];
  const nextAction = recommendations[0] || null;
  const recentQuiz = (ov?.quizzes?.recent || [])[0] || null;
  const recentProjects = projects.slice(-4).reverse();
  const newestProject = projects.length ? projects[projects.length - 1] : null;

  if (!projects.length) {
    return (
      <div className="home-wrap">
        <PageHeader
          eyebrow="Home"
          title="Welcome to AI Study Companion"
          sub="Create a space, add a project, upload a PDF — then learn with your tutor."
        />
        <EmptyState
          title="No projects yet"
          body="Your learning home will show progress, attention areas, and next actions once you start."
        />
        <button type="button" onClick={() => navigate('/spaces')} className="home-cta">
          Create your first space →
        </button>
      </div>
    );
  }

  return (
    <div className="home-wrap">
      <PageHeader
        eyebrow="Home"
        title="Welcome back"
        sub="Where you left off, how you're doing, and what to do next."
      />
      <div className="home-kpis">
        <Stat value={kpis.projects ?? projects.length} label="Projects" />
        <Stat value={`${concepts.average ?? 0}%`} label="Avg mastery" tone="up" />
        <Stat value={`${kpis.quizAccuracy ?? 0}%`} label="Quiz accuracy" tone={(kpis.quizAccuracy ?? 0) >= 60 ? 'up' : undefined} />
      </div>

      <LearningLoop ov={ov} newestProject={newestProject} navigate={navigate} />

      <div className="home-grid-2">
        <ContinueCard quiz={recentQuiz} project={newestProject} navigate={navigate} />
        <section className="home-card">
          <p className="home-eyebrow">Recommended next action</p>
          {nextAction ? (
            <>
              <h3 className="home-card-title">{nextAction.title}</h3>
              <p className="home-muted">{nextAction.text}</p>
              {nextAction.project_id && nextAction.space_id && (
                <button
                  type="button"
                  onClick={() => navigate(projBase(nextAction.space_id, nextAction.project_id))}
                  className="home-link"
                >
                  Open project →
                </button>
              )}
            </>
          ) : (
            <p className="home-muted">Nothing urgent — keep learning. Your next recommendation will appear here.</p>
          )}
        </section>
      </div>

      <div className="home-grid-2">
        <section className="home-card">
          <h3 className="home-card-title">Recent projects</h3>
          <ul className="home-list">
            {recentProjects.map((p) => {
              const avg = ov?.masteryByProject?.[p.id]?.average ?? 0;
              return (
                <li key={p.id}>
                  <button type="button" onClick={() => navigate(projBase(p.spaceId, p.id))} className="home-row">
                    <span className="home-row-main">
                      <strong>{p.name}</strong>
                      <small className="home-muted">{p.spaceName}</small>
                    </span>
                    <span className="home-row-progress">
                      <ProgressBar value={avg} />
                      <span>{avg}%</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
        <section className="home-card">
          <h3 className="home-card-title">Areas requiring attention</h3>
          {needsAttention.length === 0 ? (
            <p className="home-muted">Nothing below 40% mastery. Nice work.</p>
          ) : (
            <ul className="home-list">
              {needsAttention.map((c) => (
                <li key={c.id} className="home-attention">
                  <span>
                    <strong>{c.name}</strong>
                    <small className="home-muted">{c.project_name || ''}</small>
                  </span>
                  <StatusBadge tone="danger">{c.mastery}%</StatusBadge>
                </li>
              ))}
            </ul>
          )}
          {recommendations.length > 1 && (
            <div className="home-more-recs">
              <h4 className="home-eyebrow">More next steps</h4>
              <ul className="home-list">
                {recommendations.slice(1).map((r, i) => (
                  <li key={i}>
                    <strong>{r.title}</strong>
                    <p className="home-muted">{r.text}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
