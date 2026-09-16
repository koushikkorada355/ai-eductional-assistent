import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import {
  startQuiz, refreshQuiz, persistAnswer, submitFullQuiz,
  loadAttempts, viewAttempt, resumeAttempt, setIndex, setDraft, backToStart, resetQuiz,
} from '../../../../features/quiz/quizSlice.js';
import ConfirmModal from '../../../../components/ConfirmModal/ConfirmModal.jsx';
import { IconClipboard, IconArrowRight, IconArrowLeft, IconCheck } from '../../../../components/icons/Icons.jsx';
import './Quiz.css';

function trackerClass(q, i, index) {
  if (i === index) return 'active';
  if ((q.user_answer || '').trim()) return 'saved';
  return 'todo';
}

export default function Quiz({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const {
    view, quizId, name, questions, index, drafts,
    attempts, average, status, error,
  } = useSelector((s) => s.quiz);
  const [formName, setFormName] = useState('');
  const [formGoal, setFormGoal] = useState('');
  const [formMcq, setFormMcq] = useState(3);
  const [formOpen, setFormOpen] = useState(2);
  const [nameTouched, setNameTouched] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  const nameValid = formName.trim().length > 0;
  const totalQuestions = formMcq + formOpen;
  const countValid = totalQuestions >= 1 && totalQuestions <= 10;

  const clampCount = (v) => Math.max(0, Math.min(10, Number.isNaN(parseInt(v, 10)) ? 0 : parseInt(v, 10)));

  useEffect(() => {
    dispatch(resetQuiz());
    if (projectId) dispatch(loadAttempts({ projectId }));
  }, [dispatch, projectId]);

  useEffect(() => {
    if (view !== 'generating' && view !== 'evaluating') return;
    const t = setInterval(() => dispatch(refreshQuiz({ quizId })), 4000);
    return () => clearInterval(t);
  }, [view, quizId, dispatch]);

  const begin = (e) => {
    e.preventDefault();
    setNameTouched(true);
    if (!nameValid || !countValid) return;
    dispatch(startQuiz({ projectId, name: formName.trim(), goal: formGoal.trim(), numMcq: formMcq, numOpen: formOpen }));
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

  const unanswered = questions.filter((x) => !(x.user_answer || '').trim()).length;

  const openAttempt = (a) => {
    if (a.status === 'completed') {
      dispatch(viewAttempt({ quizId: a.id }));
    } else if (a.status !== 'failed') {
      dispatch(resumeAttempt({ quizId: a.id }));
    }
  };

  const attemptLabel = (a) => {
    if (a.status === 'completed') {
      return a.average_score != null ? `${a.average_score}%` : a.status;
    }
    if (a.status === 'in_progress') return 'Resume';
    if (a.status === 'generating') return 'Generating…';
    if (a.status === 'evaluating') return 'Grading…';
    return a.status;
  };

  const goStart = () => {
    dispatch(backToStart());
    if (projectId) dispatch(loadAttempts({ projectId }));
  };

  if (view === 'start') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card quiz-setup" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
          <div className="setup-icon"><IconClipboard /></div>
          <h3>Start a new quiz</h3>
          <p className="muted">Name your quiz and describe what to test. Questions are generated from your uploaded materials.</p>
          <form onSubmit={begin} className="quiz-form" noValidate>
            <label>Quiz name *
              <input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                onBlur={() => setNameTouched(true)}
                placeholder="e.g. Photosynthesis Basics"
                maxLength={100}
                required
              />
            </label>
            {nameTouched && !nameValid && <p className="error">Quiz name is required.</p>}
            <label>Learning goal <span className="muted">(optional — leave blank to test weakest concepts)</span>
              <textarea value={formGoal} onChange={(e) => setFormGoal(e.target.value)} placeholder="e.g. light reactions and Calvin cycle" rows={3} maxLength={500} />
            </label>
            <div className="quiz-opt-row">
              <span className="quiz-opt-label">MCQs <span className="muted">(how many)</span></span>
              <div className="quiz-stepper">
                <button type="button" className="quiz-step-btn" onClick={() => setFormMcq((v) => Math.max(0, v - 1))} disabled={formMcq <= 0}>−</button>
                <input
                  className="quiz-step-input"
                  type="number" min={0} max={10}
                  value={formMcq}
                  onChange={(e) => setFormMcq(clampCount(e.target.value))}
                />
                <button type="button" className="quiz-step-btn" onClick={() => setFormMcq((v) => Math.min(10, v + 1))} disabled={formMcq >= 10}>+</button>
              </div>
            </div>
            <div className="quiz-opt-row">
              <span className="quiz-opt-label">Open-ended <span className="muted">(how many)</span></span>
              <div className="quiz-stepper">
                <button type="button" className="quiz-step-btn" onClick={() => setFormOpen((v) => Math.max(0, v - 1))} disabled={formOpen <= 0}>−</button>
                <input
                  className="quiz-step-input"
                  type="number" min={0} max={10}
                  value={formOpen}
                  onChange={(e) => setFormOpen(clampCount(e.target.value))}
                />
                <button type="button" className="quiz-step-btn" onClick={() => setFormOpen((v) => Math.min(10, v + 1))} disabled={formOpen >= 10}>+</button>
              </div>
            </div>
            {!countValid && <p className="error">Pick 1–10 questions in total (MCQs + open-ended).</p>}
            {countValid && (
              <p className="muted small">
                Order: all {formMcq} MCQ{formMcq === 1 ? '' : 's'} first, then {formOpen} open-ended — {totalQuestions} question{totalQuestions === 1 ? '' : 's'} total.
              </p>
            )}
            <motion.button
              className="primary" type="submit"
              whileTap={{ scale: 0.98 }}
              disabled={status === 'creating' || !nameValid || !countValid}
            >
              {status === 'creating' ? 'Creating...' : <>Generate quiz · {totalQuestions} question{totalQuestions === 1 ? '' : 's'} <IconArrowRight size={18} />}</>}
            </motion.button>
          </form>
          {error && <p className="error">{error}</p>}
          {status === 'loading' && <p className="muted">Loading quiz…</p>}
        </motion.div>
        <div className="quiz-card">
          <h4>Previous attempts</h4>
          {attempts.length === 0 && <p className="muted">No attempts yet. Your completed quizzes will appear here.</p>}
          {attempts.map((a) => (
            <motion.button
              key={a.id}
              className="attempt-row"
              onClick={() => openAttempt(a)}
              disabled={a.status === 'failed' || status === 'loading'}
              whileHover={a.status !== 'failed' ? { x: 4 } : {}}
            >
              <span className="attempt-name">{a.name}</span>
              <span className={`attempt-score ${a.average_score != null && a.average_score >= 60 ? 'good' : a.average_score != null ? 'bad' : ''}`}>
                {attemptLabel(a)}
              </span>
            </motion.button>
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
          <h4>Building "{name}"</h4>
          <p className="muted">Reading your materials and crafting questions. This takes a moment...</p>
        </motion.div>
      </div>
    );
  }

  if (view === 'evaluating') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card center" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <span className="spinner" />
          <h4>Grading your quiz</h4>
          <p className="muted">Evaluating answers and updating your mastery...</p>
        </motion.div>
      </div>
    );
  }

  if (view === 'results') {
    return (
      <div className="quiz-page">
        <motion.div className="quiz-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}>
          <div className="results-head">
            <div>
              <h3>{name}</h3>
              <p className="muted">{questions.length} questions answered</p>
            </div>
            <div className={`score-ring ${average != null && average >= 60 ? 'good' : 'bad'}`}>
              {average != null ? `${average}%` : '—'}
            </div>
          </div>
          <button className="link-btn" onClick={goStart}><IconArrowLeft size={18} /> Back to quizzes</button>
          {questions.map((item, i) => {
            const ev = item.evaluation || {};
            const ok = ev.score != null && ev.score >= 60;
            return (
              <motion.div
                key={item.id}
                className={`result-q ${ok ? 'good' : 'bad'}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.05, 0.3) }}
              >
                <strong>Q{i + 1}. {item.question_text}</strong>
                <p><span className="label">Your answer:</span> {item.user_answer || '—'}</p>
                {item.question_type === 'multiple_choice' && <p><span className="label">Correct answer:</span> {item.correct_answer}</p>}
                <div className="result-score">Score {ev.score ?? '—'}</div>
                <p className="muted">{ev.feedback}</p>
                {ev.missing_concepts?.length > 0 && <small>Review: {ev.missing_concepts.join(', ')}</small>}
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    );
  }

  return (
    <div className="quiz-layout">
      <motion.div className="quiz-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} key={q?.id || 'none'}>
        <div className="quiz-progress">
          <small className="quiz-meta">Question {index + 1} of {questions.length} · {q?.question_type?.replace('_', ' ')}</small>
          <div className="progress thin"><div style={{ width: `${questions.length ? ((index + 1) / questions.length) * 100 : 0}%` }} /></div>
        </div>
        <h3>{q?.question_text}</h3>
        {q?.question_type === 'multiple_choice' ? (
          <div className="mcq-grid">
            {(q?.options || []).map((opt) => (
              <motion.button
                key={opt}
                className={draft === opt ? 'mcq selected' : 'mcq'}
                onClick={() => dispatch(setDraft({ id: q.id, value: opt }))}
                whileHover={{ scale: 1.015 }}
                whileTap={{ scale: 0.985 }}
              >
                {opt}
              </motion.button>
            ))}
          </div>
        ) : (
          <textarea value={draft} onChange={(e) => dispatch(setDraft({ id: q.id, value: e.target.value }))} placeholder="Write your answer..." rows={5} />
        )}
        <div className="quiz-actions">
          <button className="secondary" onClick={() => go(index - 1)} disabled={index === 0}><IconArrowLeft size={18} /> Previous</button>
          <motion.button className="secondary save-btn" onClick={save} disabled={!dirty || saving || !draft.trim()} whileTap={{ scale: 0.97 }}>
            {saving ? 'Saving...' : (q?.user_answer ? <><IconCheck /> Saved</> : 'Save answer')}
          </motion.button>
          <button className="secondary" onClick={() => go(index + 1)} disabled={index === questions.length - 1}>Next <IconArrowRight size={18} /></button>
        </div>
        <AnimatePresence>
          {q?.user_answer && !dirty && (
            <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="saved-note">
              <IconCheck /> Answer saved. You can change it anytime before submitting the quiz.
            </motion.p>
          )}
        </AnimatePresence>
        <button className="primary submit-quiz" onClick={() => setConfirmSubmit(true)}>Submit Quiz</button>
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
              whileHover={{ scale: 1.1 }}
              title={`Question ${i + 1}`}
            >
              {i + 1}
            </motion.button>
          ))}
        </div>
        <p className="muted small legend"><span className="dot-s saved" /> Saved <span className="dot-s active" /> Active <span className="dot-s todo" /> Unattempted</p>
      </aside>

      <ConfirmModal
        open={confirmSubmit}
        title="Submit quiz?"
        message={unanswered > 0
          ? `${unanswered} question(s) are still unanswered. Submit anyway? You cannot change answers after submitting.`
          : 'Submit the quiz for evaluation? You cannot change answers after submitting.'}
        confirmLabel="Submit"
        onConfirm={() => { setConfirmSubmit(false); dispatch(submitFullQuiz({ quizId })); }}
        onCancel={() => setConfirmSubmit(false)}
      />
    </div>
  );
}
