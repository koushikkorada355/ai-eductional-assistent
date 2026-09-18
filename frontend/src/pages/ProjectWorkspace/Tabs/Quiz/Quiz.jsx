import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import {
  startQuiz, refreshQuiz, persistAnswer, submitFullQuiz,
  loadAttempts, viewAttempt, resumeAttempt, setIndex, setDraft, backToStart, resetQuiz,
} from '../../../../features/quiz/quizSlice.js';
import ConfirmModal from '../../../../components/ConfirmModal/ConfirmModal.jsx';
import { PageHeader, Stat, StatusBadge, Spinner, ProgressBar } from '../../../../components/ui/ui.jsx';
import { IconClipboard, IconArrowRight, IconArrowLeft, IconCheck } from '../../../../components/icons/Icons.jsx';

function trackerClass(q, i, index) {
  if (i === index) return 'bg-primary text-white';
  if ((q.user_answer || '').trim()) return 'bg-accent-soft text-accent';
  return 'bg-canvas text-muted';
}

function Stepper({ label, hint, value, onChange }) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[13px] font-semibold text-ink">
        {label} <span className="font-normal text-muted">{hint}</span>
      </span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange(Math.max(0, value - 1))}
          disabled={value <= 0}
          aria-label={`Fewer ${label}`}
          className="h-9 w-10 rounded-md border border-line bg-surface text-base font-semibold text-ink hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
        >
          −
        </button>
        <input
          type="number"
          min={0}
          max={10}
          value={value}
          onChange={(e) => onChange(Math.max(0, Math.min(10, Number.isNaN(parseInt(e.target.value, 10)) ? 0 : parseInt(e.target.value, 10))))}
          aria-label={`${label} count`}
          className="h-9 w-[52px] rounded-md border border-line bg-surface text-center text-sm"
        />
        <button
          type="button"
          onClick={() => onChange(Math.min(10, value + 1))}
          disabled={value >= 10}
          aria-label={`More ${label}`}
          className="h-9 w-10 rounded-md border border-line bg-surface text-base font-semibold text-ink hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-40"
        >
          +
        </button>
      </div>
    </div>
  );
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
  const [showAllHistory, setShowAllHistory] = useState(false);

  const nameValid = formName.trim().length > 0;
  const totalQuestions = formMcq + formOpen;
  const countValid = totalQuestions >= 1 && totalQuestions <= 10;

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
  const answered = questions.length - unanswered;

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

  /* ---------------- start: understand → configure → history ---------------- */
  if (view === 'start') {
    const completed = attempts.filter((a) => a.status === 'completed');
    const scores = completed.map((a) => a.average_score).filter((s) => s != null);
    const best = scores.length ? Math.max(...scores) : null;
    const active = attempts.filter((a) => a.status === 'in_progress' || a.status === 'generating' || a.status === 'evaluating');
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Quiz"
          title="Quizzes"
          sub="Test yourself with questions generated from your uploaded materials."
        />
        {(attempts.length > 0) && (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat value={attempts.length} label="Attempts" tone="accent" />
            <Stat value={completed.length} label="Completed" tone="up" />
            <Stat value={best != null ? `${best}%` : '—'} label="Best score" tone={best != null && best >= 60 ? 'up' : undefined} />
            <Stat value={active.length} label="In progress" tone={active.length ? 'accent' : undefined} />
          </div>
        )}
        <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-5">
          {/* Primary action first: build a new quiz */}
          <motion.div
            className="rounded-card border border-line bg-surface p-6 shadow-sm xl:col-span-3"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <div className="flex items-center gap-3">
              <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-soft text-primary [&>svg]:h-[22px] [&>svg]:w-[22px]">
                <IconClipboard />
              </span>
              <div>
                <h3 className="font-display text-base font-bold text-heading">Start a new quiz</h3>
                <p className="text-[13px] text-muted">Name it, pick a mix, generate — questions come from your materials.</p>
              </div>
            </div>
            <form onSubmit={begin} className="mt-4 flex flex-col gap-4" noValidate>
              <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink">
                Quiz name *
                <input
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  onBlur={() => setNameTouched(true)}
                  placeholder="e.g. Photosynthesis Basics"
                  maxLength={100}
                  required
                  className="min-h-9 rounded-md border border-line bg-surface px-3 text-sm font-normal"
                />
              </label>
              {nameTouched && !nameValid && <p className="error">Quiz name is required.</p>}
              <label className="flex flex-col gap-1.5 text-[13px] font-semibold text-ink">
                Learning goal <span className="font-normal text-muted">(optional — leave blank to test weakest concepts)</span>
                <textarea
                  value={formGoal}
                  onChange={(e) => setFormGoal(e.target.value)}
                  placeholder="e.g. light reactions and Calvin cycle"
                  rows={3}
                  maxLength={500}
                  className="rounded-md border border-line bg-surface px-3 py-2 text-sm font-normal"
                />
              </label>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Stepper label="MCQs" hint="(how many)" value={formMcq} onChange={setFormMcq} />
                <Stepper label="Open-ended" hint="(how many)" value={formOpen} onChange={setFormOpen} />
              </div>
              {!countValid && <p className="error">Pick 1–10 questions in total (MCQs + open-ended).</p>}
              {countValid && (
                <p className="text-[11px] text-muted">
                  Order: all {formMcq} MCQ{formMcq === 1 ? '' : 's'} first, then {formOpen} open-ended — {totalQuestions} question{totalQuestions === 1 ? '' : 's'} total.
                </p>
              )}
              <motion.button
                className="inline-flex min-h-10 w-full items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 [&>svg]:h-[18px] [&>svg]:w-[18px]"
                type="submit"
                whileTap={{ scale: 0.98 }}
                disabled={status === 'creating' || !nameValid || !countValid}
              >
                {status === 'creating' ? 'Creating...' : <>Generate quiz · {totalQuestions} question{totalQuestions === 1 ? '' : 's'} <IconArrowRight size={18} /></>}
              </motion.button>
            </form>
            {error && <p className="error mt-3">{error}</p>}
            {status === 'loading' && <p className="mt-3 text-[13px] text-muted">Loading quiz…</p>}
          </motion.div>

          {/* Secondary: recent history with status at a glance */}
          <div className="rounded-card border border-line bg-surface p-6 shadow-sm xl:col-span-2">
            <h3 className="font-display text-sm font-semibold text-heading">Previous quizzes</h3>
            <p className="mt-0.5 text-[13px] text-muted">Resume where you left off or review a graded quiz.</p>
            <div className="mt-3 flex flex-col gap-2">
              {attempts.length === 0 && (
                <p className="text-[13px] text-muted">No attempts yet. Your quizzes will appear here.</p>
              )}
              {(showAllHistory ? attempts : attempts.slice(0, 5)).map((a) => {
                const disabled = a.status === 'failed' || status === 'loading';
                const score = a.average_score;
                return (
                  <motion.button
                    key={a.id}
                    onClick={() => openAttempt(a)}
                    disabled={disabled}
                    whileHover={disabled ? {} : { x: 4 }}
                    className="flex w-full items-center gap-3 rounded-md border border-line bg-surface px-4 py-3 text-left hover:border-primary disabled:cursor-default"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-ink">{a.name}</span>
                      <span className="mt-0.5 block"><StatusBadge status={a.status}>{attemptLabel(a)}</StatusBadge></span>
                    </span>
                    {a.status === 'completed' && score != null && (
                      <span className={`shrink-0 font-display text-lg font-bold ${score >= 60 ? 'text-accent' : 'text-danger'}`}>
                        {score}%
                      </span>
                    )}
                    <IconArrowRight size={18} className="shrink-0 text-muted" />
                  </motion.button>
                );
              })}
              {attempts.length > 5 && (
                <button
                  type="button"
                  onClick={() => setShowAllHistory((v) => !v)}
                  aria-expanded={showAllHistory}
                  className="mt-1 inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:border-primary hover:text-primary"
                >
                  {showAllHistory ? 'Show less' : `View all ${attempts.length} quizzes →`}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'generating' || view === 'evaluating') {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Quiz" title={view === 'generating' ? 'Building your quiz' : 'Grading your quiz'} />
        <motion.div
          className="flex flex-col items-center gap-3 rounded-card border border-line bg-surface px-6 py-12 text-center shadow-sm"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <Spinner label={view === 'generating' ? `Reading your materials and crafting “${name}”. This takes a moment…` : 'Evaluating answers and updating your mastery…'} />
        </motion.div>
      </div>
    );
  }

  /* ---------------- results: score hero → mistake review ---------------- */
  if (view === 'results') {
    const passed = average != null && average >= 60;
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Quiz results" title={name} sub={`${questions.length} questions answered`} />
        <motion.div
          className="flex flex-col items-center gap-1 rounded-card border border-line bg-surface px-6 py-8 text-center shadow-sm"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <span className={`font-display text-5xl font-bold leading-none ${passed ? 'text-accent' : 'text-danger'}`}>
            {average != null ? `${average}%` : '—'}
          </span>
          <StatusBadge tone={passed ? 'success' : 'danger'}>{passed ? 'Passed' : 'Needs review'}</StatusBadge>
          <button
            type="button"
            onClick={goStart}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]"
          >
            <IconArrowLeft size={18} /> Back to quizzes
          </button>
        </motion.div>
        <h3 className="font-display text-sm font-semibold text-heading">Review your answers</h3>
        <div className="flex flex-col gap-3">
          {questions.map((item, i) => {
            const ev = item.evaluation || {};
            const ok = ev.score != null && ev.score >= 60;
            return (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.05, 0.3) }}
                className={`flex flex-col gap-1.5 rounded-md border bg-surface p-4 text-sm shadow-sm ${ok ? 'border-accent/30' : 'border-danger/30'}`}
              >
                <strong className="text-sm text-ink">Q{i + 1}. {item.question_text}</strong>
                <p><span className="font-semibold text-heading">Your answer:</span> {item.user_answer || '—'}</p>
                {item.question_type === 'multiple_choice' && <p><span className="font-semibold text-heading">Correct answer:</span> {item.correct_answer}</p>}
                <div className="flex items-center gap-2">
                  <StatusBadge tone={ok ? 'success' : 'danger'}>Score {ev.score ?? '—'}</StatusBadge>
                </div>
                <p className="text-muted">{ev.feedback}</p>
                {ev.missing_concepts?.length > 0 && <small className="text-muted">Review: {ev.missing_concepts.join(', ')}</small>}
              </motion.div>
            );
          })}
        </div>
      </div>
    );
  }

  /* ---------------- answering: progress → question → navigate → submit ---------------- */
  return (
    <div className="flex flex-col gap-6">
      <PageHeader eyebrow="Quiz in progress" title={name} sub={`Question ${index + 1} of ${questions.length} · ${q?.question_type?.replace('_', ' ')}`} />
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start">
        <motion.div
          className="flex min-w-0 flex-1 flex-col gap-4 rounded-card border border-line bg-surface p-6 shadow-sm"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          key={q?.id || 'none'}
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs font-medium text-muted">
              <span>Question {index + 1} of {questions.length}</span>
              <span>{answered}/{questions.length} saved</span>
            </div>
            <ProgressBar value={questions.length ? ((index + 1) / questions.length) * 100 : 0} />
          </div>
          <h3 className="font-display text-base font-bold text-ink">{q?.question_text}</h3>
          {q?.question_type === 'multiple_choice' ? (
            <div className="flex flex-col gap-2" role="radiogroup" aria-label="Answer options">
              {(q?.options || []).map((opt, oi) => {
                const selected = draft === opt;
                return (
                  <motion.button
                    key={opt}
                    onClick={() => dispatch(setDraft({ id: q.id, value: opt }))}
                    whileHover={{ scale: 1.005 }}
                    whileTap={{ scale: 0.995 }}
                    role="radio"
                    aria-checked={selected}
                    aria-pressed={selected}
                    aria-label={`Option ${String.fromCharCode(65 + oi)}: ${opt}${selected ? ' (selected)' : ''}`}
                    className={`flex items-center gap-3 rounded-md border px-3.5 py-3 text-left text-sm transition-colors ${
                      selected
                        ? 'border-primary bg-primary-soft font-semibold text-primary shadow-sm ring-1 ring-primary'
                        : 'border-line bg-surface font-normal text-ink hover:border-primary'
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-bold ${
                        selected ? 'border-primary bg-primary text-white' : 'border-line bg-canvas text-muted'
                      }`}
                    >
                      {String.fromCharCode(65 + oi)}
                    </span>
                    <span className="min-w-0 flex-1">{opt}</span>
                    {selected && (
                      <span className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-white [&>svg]:h-3.5 [&>svg]:w-3.5" aria-hidden="true">
                        <IconCheck />
                      </span>
                    )}
                  </motion.button>
                );
              })}
            </div>
          ) : (
            <textarea
              value={draft}
              onChange={(e) => dispatch(setDraft({ id: q.id, value: e.target.value }))}
              placeholder="Write your answer..."
              rows={5}
              className="rounded-md border border-line bg-surface px-3 py-2 text-sm"
            />
          )}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => go(index - 1)}
              disabled={index === 0}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50 [&>svg]:h-[18px] [&>svg]:w-[18px]"
            >
              <IconArrowLeft size={18} /> Previous
            </button>
            <motion.button
              type="button"
              onClick={save}
              disabled={!dirty || saving || !draft.trim()}
              whileTap={{ scale: 0.97 }}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50 [&>svg]:h-4 [&>svg]:w-4"
            >
              {saving ? 'Saving...' : (q?.user_answer ? <><IconCheck /> Saved</> : 'Save answer')}
            </motion.button>
            <button
              type="button"
              onClick={() => go(index + 1)}
              disabled={index === questions.length - 1}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-md border border-line bg-surface px-3 text-xs font-medium text-ink hover:bg-canvas disabled:opacity-50 [&>svg]:h-[18px] [&>svg]:w-[18px]"
            >
              Next <IconArrowRight size={18} />
            </button>
            <span className="ml-auto text-xs text-muted">{unanswered} unanswered</span>
          </div>
          <AnimatePresence>
            {q?.user_answer && !dirty && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 text-[13px] text-accent [&>svg]:h-4 [&>svg]:w-4"
              >
                <IconCheck /> Answer saved. You can change it anytime before submitting the quiz.
              </motion.p>
            )}
          </AnimatePresence>
          <button
            type="button"
            onClick={() => setConfirmSubmit(true)}
            className="inline-flex min-h-10 w-full items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
          >
            Submit Quiz
          </button>
        </motion.div>

        <aside className="order-first w-full shrink-0 rounded-card border border-line bg-surface p-4 shadow-sm lg:order-none lg:sticky lg:top-[76px] lg:w-44" aria-label="Question navigator">
          <h4 className="truncate text-[13px] font-semibold text-ink">{name}</h4>
          <div className="mt-3 flex flex-row flex-wrap gap-1.5 lg:grid lg:grid-cols-4">
            {questions.map((item, i) => (
              <motion.button
                key={item.id}
                onClick={() => go(i)}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={{ scale: 1.08 }}
                title={`Question ${i + 1}`}
                aria-label={`Go to question ${i + 1}`}
                aria-current={i === index ? 'true' : undefined}
                className={`h-8 w-8 rounded-md text-xs font-semibold ${trackerClass(item, i, index)}`}
              >
                {i + 1}
              </motion.button>
            ))}
          </div>
          <p className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
            <span className="inline-block h-2.5 w-2.5 rounded-[3px] border border-accent bg-accent-soft" /> Saved
            <span className="inline-block h-2.5 w-2.5 rounded-[3px] bg-primary" /> Active
            <span className="inline-block h-2.5 w-2.5 rounded-[3px] bg-line" /> Unattempted
          </p>
        </aside>
      </div>

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
