import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import {
  startQuiz, refreshQuiz, persistAnswer, submitFullQuiz,
  loadAttempts, viewAttempt, setIndex, setDraft, backToStart,
} from '../../../../features/quiz/quizSlice.js';
import './Quiz.css';

function trackerClass(q, i, index) {
  if (i === index) return 'active';
  if ((q.user_answer || '').trim()) return 'saved';
  return 'todo';
}

export default function Quiz({ projectId }) {
  const dispatch = useDispatch();
  const {
    view, quizId, name, questions, index, drafts,
    attempts, average, status, error,
  } = useSelector((s) => s.quiz);
  const [formName, setFormName] = useState('');
  const [formGoal, setFormGoal] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    dispatch({ type: 'quiz/resetQuiz' });
    if (projectId) dispatch(loadAttempts({ projectId }));
  }, [dispatch, projectId]);

  useEffect(() => {
    if (view !== 'generating' && view !== 'evaluating') return;
    const t = setInterval(() => dispatch(refreshQuiz({ quizId })), 4000);
    return () => clearInterval(t);
  }, [view, quizId, dispatch]);

  const begin = (e) => {
    e.preventDefault();
    if (!formName.trim() || !formGoal.trim()) return;
    dispatch(startQuiz({ projectId, name: formName.trim(), goal: formGoal.trim() }));
  };

  const q = questions[index];
  const draft = q ? (drafts[q.id] ?? '') : '';
  const dirty = q ? draft.trim() !== (q.user_answer || '').trim() : false;

  const save = async () => {
    if (!q || !draft.trim() || !dirty) return;
    setSaving(true);
    await dispatch(persistAnswer({ quizId, questionId: q.id, answer: draft.trim() }));
    setSaving(false);
  };

  const go = (i) => {
    if (i >= 0 && i < questions.length) dispatch(setIndex(i));
  };

  const submitAll = () => {
    const unanswered = questions.filter((x) => !(x.user_answer || '').trim()).length;
    const msg = unanswered > 0
      ? `${unanswered} question(s) unanswered. Submit the quiz anyway?`
      : 'Submit the quiz for evaluation? You cannot change answers after submitting.';
    if (window.confirm(msg)) dispatch(submitFullQuiz({ quizId }));
  };

  const openAttempt = (a) => {
    if (a.status === 'completed') dispatch(viewAttempt({ quizId: a.id }));
  };

  if (view === 'start') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <h3>Start a new quiz</h3>
          <p className="muted">Name your quiz and describe what to test. Questions are generated from your uploaded materials.</p>
          <form onSubmit={begin} className="quiz-form">
            <input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="Quiz name (e.g. Photosynthesis Basics)" maxLength={100} />
            <textarea value={formGoal} onChange={(e) => setFormGoal(e.target.value)} placeholder="Learning goal (e.g. light reactions and Calvin cycle)" rows={3} maxLength={500} />
            <button className="primary" type="submit" disabled={status === 'creating' || !formName.trim() || !formGoal.trim()}>
              {status === 'creating' ? 'Creating...' : 'Generate quiz'}
            </button>
          </form>
          {error && <p className="error">{error}</p>}
        </motion.div>
        <div className="quiz-card">
          <h4>Previous attempts</h4>
          {attempts.length === 0 && <p className="muted">No attempts yet.</p>}
          {attempts.map((a) => (
            <button key={a.id} className="attempt-row" onClick={() => openAttempt(a)} disabled={a.status !== 'completed'}>
              <span>{a.name}</span>
              <span className="muted">{a.average_score != null ? `${a.average_score}%` : a.status}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (view === 'generating') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card center" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <span className="spinner" />
          <p>Generating "{name}" from your materials. This takes a moment...</p>
        </motion.div>
      </div>
    );
  }

  if (view === 'evaluating') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card center" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <span className="spinner" />
          <p>Evaluating your answers and updating mastery...</p>
        </motion.div>
      </div>
    );
  }

  if (view === 'results') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <h3>{name} — Score: {average != null ? `${average}%` : '—'}</h3>
          <button className="link-btn" onClick={() => dispatch(backToStart())}>← Back to quizzes</button>
          {questions.map((item, i) => {
            const ev = item.evaluation || {};
            const ok = ev.score != null && ev.score >= 60;
            return (
              <div key={item.id} className={`result-q ${ok ? 'good' : 'bad'}`}>
                <strong>Q{i + 1}. {item.question_text}</strong>
                <p>Your answer: {item.user_answer || '—'}</p>
                {item.question_type === 'multiple_choice' && <p>Correct answer: {item.correct_answer}</p>}
                <p className="muted">Score {ev.score ?? '—'} · {ev.feedback}</p>
                {ev.missing_concepts?.length > 0 && <small>Review: {ev.missing_concepts.join(', ')}</small>}
              </div>
            );
          })}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="quiz-layout">
      <motion.div className="quiz-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} key={q?.id || 'none'}>
        <small className="quiz-meta">Question {index + 1} of {questions.length} · {q?.question_type}</small>
        <h3>{q?.question_text}</h3>
        {q?.question_type === 'multiple_choice' ? (
          <div className="mcq-grid">
            {(q?.options || []).map((opt) => (
              <button key={opt} className={draft === opt ? 'mcq selected' : 'mcq'} onClick={() => dispatch(setDraft({ id: q.id, value: opt }))}>
                {opt}
              </button>
            ))}
          </div>
        ) : (
          <textarea value={draft} onChange={(e) => dispatch(setDraft({ id: q.id, value: e.target.value }))} placeholder="Write your answer..." rows={5} />
        )}
        <div className="quiz-actions">
          <button className="secondary" onClick={() => go(index - 1)} disabled={index === 0}>← Previous</button>
          <button className="secondary" onClick={save} disabled={!dirty || saving || !draft.trim()}>
            {saving ? 'Saving...' : (q?.user_answer ? 'Save' : 'Save answer')}
          </button>
          <button className="secondary" onClick={() => go(index + 1)} disabled={index === questions.length - 1}>Next →</button>
        </div>
        <AnimatePresence>
          {q?.user_answer && !dirty && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="saved-note">
              Answer saved. You can change it anytime before submitting the quiz.
            </motion.p>
          )}
        </AnimatePresence>
        <button className="primary" onClick={submitAll}>Submit Quiz</button>
      </motion.div>

      <aside className="tracker">
        <h4>{name}</h4>
        <div className="tracker-list">
          {questions.map((item, i) => (
            <motion.button
              key={item.id}
              className={`tracker-num ${trackerClass(item, i, index)}`}
              onClick={() => go(i)}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
            >
              {i + 1}
            </motion.button>
          ))}
        </div>
        <p className="muted small">Green = saved · Yellow = active · Grey = unattempted</p>
      </aside>
    </div>
  );
}
