import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { loadAssignments, createAssignmentThunk, loadAssignment, submitAssignmentThunk, clearSelected } from '../../../../features/assignments/assignmentsSlice.js';
import { loadConcepts } from '../../../../features/concepts/conceptsSlice.js';
import ConfirmModal from '../../../../components/ConfirmModal/ConfirmModal.jsx';
import { PageHeader, Stat, StatusBadge, EmptyState, Spinner, ProgressBar } from '../../../../components/ui/ui.jsx';
import { IconArrowRight, IconArrowLeft, IconPlus } from '../../../../components/icons/Icons.jsx';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'ready', label: 'Ready to take' },
  { id: 'active', label: 'In progress' },
  { id: 'submitted', label: 'Submitted' },
];

function filterMatch(a, f) {
  if (f === 'all') return true;
  if (f === 'ready') return a.status === 'ready';
  if (f === 'active') return ['generating', 'evaluating'].includes(a.status);
  if (f === 'submitted') return a.status === 'submitted';
  return true;
}

export default function Assignments({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { assignments, selectedAssignment, status, error } = useSelector((s) => s.assignments);
  const { concepts } = useSelector((s) => s.concepts);

  const [view, setView] = useState('list');
  const [filter, setFilter] = useState('all');
  const [selectedConcepts, setSelectedConcepts] = useState([]);
  const [title, setTitle] = useState('');
  const [numQuestions, setNumQuestions] = useState(5);
  const [answers, setAnswers] = useState({});
  const [confirmSubmit, setConfirmSubmit] = useState(false);

  useEffect(() => {
    if (projectId && spaceId) {
      dispatch(loadAssignments({ spaceId, projectId }));
    }
  }, [dispatch, projectId, spaceId]);

  useEffect(() => {
    if (view === 'select-concepts' && projectId && spaceId) {
      dispatch(loadConcepts({ spaceId, projectId }));
    }
  }, [dispatch, view, projectId, spaceId]);

  const toggleConcept = (id) => {
    setSelectedConcepts((prev) =>
      prev.includes(id) ? prev.filter((c) => c !== id) : [...prev, id]
    );
  };

  const selectOption = (questionId, option) => {
    if (selectedAssignment?.status === 'submitted' || selectedAssignment?.status === 'evaluating') return;
    setAnswers((prev) => ({ ...prev, [questionId]: option }));
  };

  const handleCreate = async () => {
    if (selectedConcepts.length === 0) return;
    const safeCount = Math.max(1, Math.min(50, Number(numQuestions) || 5));
    try {
      await dispatch(createAssignmentThunk({
        spaceId,
        projectId,
        conceptIds: selectedConcepts,
        numQuestions: safeCount,
        title: title || undefined,
      })).unwrap();
      setView('generating');
      setSelectedConcepts([]);
      setTitle('');
      setNumQuestions(5);
      setAnswers({});
    } catch (e) {
      console.error('Failed to create assignment:', e);
    }
  };

  const handleSubmit = async () => {
    const questions = selectedAssignment?.questions || [];
    const unanswered = questions.filter((q) => !answers[q.id]);
    if (unanswered.length > 0) {
      setConfirmSubmit(true);
      return;
    }
    await doSubmit();
  };

  const doSubmit = async () => {
    setConfirmSubmit(false);
    try {
      await dispatch(submitAssignmentThunk({
        spaceId,
        projectId,
        assignmentId: selectedAssignment.id,
        answers,
      })).unwrap();
    } catch (e) {
      console.error('Failed to submit:', e);
    }
  };

  const handleView = async (assignment) => {
    setAnswers({});
    const detail = await dispatch(loadAssignment({ spaceId, projectId, assignmentId: assignment.id })).unwrap();
    setView(detail.status === 'generating' ? 'generating' : 'view');
  };

  const handleBack = () => {
    dispatch(clearSelected());
    setAnswers({});
    setView('list');
    dispatch(loadAssignments({ spaceId, projectId }));
  };

  const answeredCount = Object.keys(answers).length;
  const totalCount = selectedAssignment?.questions?.length || 0;
  const unansweredCount = (selectedAssignment?.questions || []).filter((q) => !answers[q.id]).length;
  const detailStatus = selectedAssignment?.status;
  const isSubmitted = detailStatus === 'submitted';
  const isEvaluating = detailStatus === 'evaluating';
  const isReady = detailStatus === 'ready';

  // Poll while the graph works in the background (generation or grading).
  useEffect(() => {
    const polling = view === 'generating' || isEvaluating;
    if (!polling || !selectedAssignment?.id) return;
    const t = setInterval(() => {
      dispatch(loadAssignment({ spaceId, projectId, assignmentId: selectedAssignment.id }));
    }, 4000);
    return () => clearInterval(t);
  }, [view, isEvaluating, selectedAssignment?.id, dispatch, spaceId, projectId]);

  // Generation finished -> take the assignment.
  useEffect(() => {
    if (view === 'generating' && detailStatus === 'ready') {
      setAnswers({});
      setView('view');
    }
  }, [view, detailStatus]);

  const stats = useMemo(() => {
    const list = assignments || [];
    const ready = list.filter((a) => a.status === 'ready').length;
    const active = list.filter((a) => ['generating', 'evaluating'].includes(a.status)).length;
    const submitted = list.filter((a) => a.status === 'submitted');
    const scored = submitted.filter((a) => a.total != null && a.total > 0);
    const avg = scored.length
      ? Math.round(scored.reduce((s, a) => s + (a.score / a.total) * 100, 0) / scored.length)
      : null;
    return { total: list.length, ready, active, submitted: submitted.length, avg };
  }, [assignments]);

  const visible = useMemo(
    () => (assignments || []).filter((a) => filterMatch(a, filter)),
    [assignments, filter]
  );
  // Previous-assignments history: show recent first, expand on demand.
  const [showAllHistory, setShowAllHistory] = useState(false);
  useEffect(() => { setShowAllHistory(false); }, [filter]);
  const shown = showAllHistory ? visible : visible.slice(0, 5);

  /* ---------------- list: status at a glance → filter → open ---------------- */
  if (view === 'list') {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Assignments"
          title="Assignments"
          sub="Practice sets generated from your concepts. Take the ones that are ready, review the ones you submitted."
          actions={(
            <button
              type="button"
              onClick={() => setView('create')}
              className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark [&>svg]:h-4 [&>svg]:w-4"
            >
              <IconPlus size={16} /> New Assignment
            </button>
          )}
        />
        {stats.total > 0 && (
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
            <Stat value={stats.total} label="Total" tone="accent" />
            <Stat value={stats.ready} label="Ready to take" tone={stats.ready ? 'accent' : undefined} />
            <Stat value={stats.active} label="In progress" tone={stats.active ? 'accent' : undefined} />
            <Stat value={stats.submitted} label="Submitted" tone="up" />
            <Stat value={stats.avg != null ? `${stats.avg}%` : '—'} label="Average score" tone={stats.avg != null && stats.avg >= 60 ? 'up' : undefined} />
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
        <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Filter assignments">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              role="tab"
              aria-selected={filter === f.id}
              onClick={() => setFilter(f.id)}
              className={`rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${
                filter === f.id
                  ? 'bg-primary font-semibold text-white'
                  : 'bg-surface text-muted hover:bg-canvas hover:text-ink'
              } border ${filter === f.id ? 'border-primary' : 'border-line'}`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <motion.div
          key={filter}
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          className="overflow-hidden rounded-card border border-line bg-surface shadow-sm"
        >
          {visible.length > 0 && (
            <div className="border-b border-line px-4 py-2.5 sm:px-5">
              <h3 className="font-display text-sm font-semibold text-heading">
                Previous assignments <span className="font-body text-xs font-medium text-muted">· {visible.length}</span>
              </h3>
            </div>
          )}
          {visible.length === 0 ? (
            <div className="p-4">
              <EmptyState
                title={assignments.length === 0 ? 'No assignments yet' : 'Nothing matches this filter'}
                body={assignments.length === 0
                  ? 'Create one to test your understanding — it takes less than a minute.'
                  : 'Try a different filter to find your assignments.'}
                actions={assignments.length === 0 && (
                  <button
                    type="button"
                    onClick={() => setView('create')}
                    className="inline-flex min-h-9 items-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
                  >
                    <IconPlus size={16} /> New Assignment
                  </button>
                )}
              />
            </div>
          ) : (
            <>
            <ul className="divide-y divide-line">
              {shown.map((a) => (
                <li key={a.id}>
                  <button
                    type="button"
                    onClick={() => handleView(a)}
                    aria-label={`Open assignment ${a.title || 'Assignment'}`}
                    className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-canvas sm:px-5"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-ink">
                        {a.title || 'Assignment'}
                      </span>
                      <span className="mt-0.5 block truncate text-xs text-muted">
                        {a.num_questions ?? 0} MCQ(s)
                        {a.created_at ? ` · ${new Date(a.created_at).toLocaleDateString()}` : ''}
                      </span>
                    </span>
                    {a.status === 'submitted' && a.total != null && (
                      <span className={`shrink-0 font-display text-base font-bold ${a.score === a.total ? 'text-accent' : a.score / a.total >= 0.5 ? 'text-info' : 'text-danger'}`}>
                        {a.score}/{a.total}
                      </span>
                    )}
                    <span className="hidden shrink-0 sm:inline"><StatusBadge status={a.status} /></span>
                    <IconArrowRight size={18} className="shrink-0 text-muted" />
                  </button>
                </li>
              ))}
            </ul>
            {visible.length > 5 && (
              <button
                type="button"
                onClick={() => setShowAllHistory((v) => !v)}
                aria-expanded={showAllHistory}
                className="flex w-full items-center justify-center border-t border-line px-4 py-3 text-sm font-medium text-muted transition-colors hover:bg-canvas hover:text-primary"
              >
                {showAllHistory ? 'Show less' : `View all ${visible.length} assignments →`}
              </button>
            )}
            </>
          )}
        </motion.div>
      </div>
    );
  }

  /* ---------------- create: 3-step builder ---------------- */
  if (view === 'create' || view === 'select-concepts') {
    const picking = view === 'select-concepts';
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="New assignment" title="Create assignment" sub="Generates multiple MCQ questions from your concepts, grounded in your materials." />
        {error && <div className="error-banner">{error}</div>}
        <AnimatePresence mode="wait">
          {!picking ? (
            <motion.div
              key="create"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="flex max-w-2xl flex-col gap-5 rounded-card border border-line bg-surface p-6 shadow-sm"
            >
              <div className="flex flex-col gap-2">
                <h3 className="text-[13px] font-semibold text-ink">
                  <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">1</span>
                  Select concepts
                </h3>
                <button
                  type="button"
                  onClick={() => setView('select-concepts')}
                  className="min-h-9 rounded-md border border-line bg-surface px-3 text-left text-sm text-ink hover:border-primary"
                >
                  {selectedConcepts.length > 0 ? `${selectedConcepts.length} concept(s) selected` : 'Select concepts...'}
                </button>
              </div>
              <div className="flex flex-col gap-2">
                <h3 className="text-[13px] font-semibold text-ink">
                  <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">2</span>
                  Title <span className="font-normal text-muted">(optional)</span>
                </h3>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g., Photosynthesis Practice Set"
                  maxLength={200}
                  className="min-h-9 w-full rounded-md border border-line bg-surface px-3 text-sm"
                />
              </div>
              <div className="flex flex-col gap-2">
                <h3 className="text-[13px] font-semibold text-ink">
                  <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary-soft text-[11px] font-bold text-primary">3</span>
                  Number of questions <span className="font-normal text-muted">(1–50, pick any)</span>
                </h3>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min={1}
                    max={50}
                    step={1}
                    value={numQuestions}
                    onChange={(e) => setNumQuestions(Number(e.target.value))}
                    aria-label="Number of questions"
                    className="h-2 flex-1 accent-primary"
                  />
                  <input
                    type="number"
                    min={1}
                    max={50}
                    step={1}
                    value={numQuestions}
                    onChange={(e) => {
                      const v = parseInt(e.target.value, 10);
                      if (Number.isNaN(v)) return;
                      setNumQuestions(Math.max(1, Math.min(50, v)));
                    }}
                    onBlur={(e) => {
                      const v = parseInt(e.target.value, 10);
                      if (Number.isNaN(v) || v < 1) setNumQuestions(1);
                      else if (v > 50) setNumQuestions(50);
                    }}
                    aria-label="Custom number of questions"
                    className="h-9 w-20 rounded-md border border-line bg-surface px-2 text-center text-sm font-semibold text-ink"
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {[5, 10, 20, 30, 50].map((n) => (
                    <button
                      key={n}
                      type="button"
                      onClick={() => setNumQuestions(n)}
                      aria-pressed={numQuestions === n}
                      className={`h-8 min-w-11 rounded-md border px-2 text-[13px] font-semibold ${
                        numQuestions === n
                          ? 'border-primary bg-primary text-white'
                          : 'border-line bg-surface text-ink hover:border-primary'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-muted">Drag the slider or type any number from 1 to 50.</p>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setView('list')}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                >
                  Back
                </button>
                <button
                  type="button"
                  disabled={selectedConcepts.length === 0 || status === 'loading'}
                  onClick={handleCreate}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                >
                  {status === 'loading' ? 'Generating MCQs...' : `Generate ${numQuestions} MCQs`}
                </button>
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="select-concepts"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="flex max-w-2xl flex-col gap-4 rounded-card border border-line bg-surface p-6 shadow-sm"
            >
              <div>
                <h3 className="font-display text-base font-bold text-ink">Select concepts</h3>
                <p className="text-[13px] text-muted">Click to select/deselect concepts.</p>
              </div>
              <div className="flex max-h-[360px] flex-col overflow-y-auto rounded-md border border-line">
                {(concepts || []).length === 0 ? (
                  <p className="p-4 text-[13px] text-muted">No concepts found. Upload a PDF to generate concepts first.</p>
                ) : (
                  (concepts || []).map((c) => {
                    const raw = c.mastery_level ?? c.mastery ?? 0;
                    const n = Number(raw);
                    const score = Math.min(100, Math.max(0, Math.round(Number.isFinite(n) ? n : 0)));
                    return (
                      <label key={c.id} className="flex cursor-pointer items-start gap-3 border-b border-line px-3.5 py-3 last:border-b-0 hover:bg-canvas">
                        <input
                          type="checkbox"
                          checked={selectedConcepts.includes(c.id)}
                          onChange={() => toggleConcept(c.id)}
                          className="mt-0.5 h-4 w-4 accent-primary"
                        />
                        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <span className="text-sm font-semibold text-heading">{c.name}</span>
                          {c.description && <span className="text-xs text-muted">{c.description}</span>}
                          <span className="mt-1 flex items-center gap-2">
                            <span className="h-1.5 max-w-[200px] flex-1 overflow-hidden rounded-full bg-canvas">
                              <span
                                className={`block h-full rounded-full ${score >= 70 ? 'bg-accent' : score >= 40 ? 'bg-primary' : 'bg-danger'}`}
                                style={{ width: `${score}%` }}
                              />
                            </span>
                            <span className="whitespace-nowrap text-[11px] text-muted">{score}% mastery</span>
                          </span>
                        </span>
                      </label>
                    );
                  })
                )}
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setView('create')}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => setView('create')}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
                >
                  Done{selectedConcepts.length > 0 ? ` (${selectedConcepts.length})` : ''}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    );
  }

  /* ---------------- generating ---------------- */
  if (view === 'generating' && detailStatus !== 'ready') {
    const failed = selectedAssignment?.status === 'failed';
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Assignment" title={failed ? 'Generation failed' : `Building “${selectedAssignment?.title || 'your assignment'}”`} />
        <div className="flex flex-col items-center gap-3 rounded-card border border-line bg-surface px-6 py-12 text-center shadow-sm">
          {failed ? (
            <>
              <p className="text-sm text-muted">The graph could not generate questions for this assignment.</p>
              <button
                type="button"
                onClick={handleBack}
                className="mt-1 inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
              >
                Back to Assignments
              </button>
            </>
          ) : (
            <>
              <Spinner label="Reading your materials and crafting MCQs in the background. This takes a moment…" />
              <button
                type="button"
                onClick={handleBack}
                className="mt-1 inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
              >
                Back to Assignments
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  /* ---------------- detail: sticky action bar → answer → submit ---------------- */
  return (
    <div className="flex flex-col gap-4">
      <div className="sticky top-[60px] z-10 -mx-1 rounded-card border border-line bg-surface/95 px-4 py-3 shadow-sm backdrop-blur">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handleBack}
            className="inline-flex min-h-9 items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]"
          >
            <IconArrowLeft size={18} /> <span className="hidden sm:inline">Assignments</span>
          </button>
          <span className="min-w-0 flex-1 truncate font-display text-[15px] font-bold text-ink">
            {selectedAssignment?.title || 'Assignment'}
          </span>
          <StatusBadge status={detailStatus} />
          {isReady && totalCount > 0 && (
            <span className="hidden text-xs font-semibold text-muted md:inline">
              {answeredCount}/{totalCount} answered
            </span>
          )}
          {isReady && (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={status === 'loading' || totalCount === 0}
              className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
            >
              {status === 'loading' ? 'Submitting...' : `Submit (${answeredCount}/${totalCount})`}
            </button>
          )}
        </div>
        {isReady && totalCount > 0 && (
          <ProgressBar value={(answeredCount / totalCount) * 100} className="mt-2" />
        )}
      </div>

      {error && <div className="error-banner">{error}</div>}

      {isSubmitted && selectedAssignment.total != null && (
        <div className={`rounded-md p-4 text-sm ${selectedAssignment.score === selectedAssignment.total ? 'bg-accent-soft text-accent' : selectedAssignment.score / selectedAssignment.total >= 0.5 ? 'bg-info-soft text-info' : 'bg-danger-soft text-danger'}`}>
          <strong className="block font-display text-lg">Score: {selectedAssignment.score}/{selectedAssignment.total}</strong>
          {selectedAssignment.feedback?.overall && <p className="mt-1">{selectedAssignment.feedback.overall}</p>}
        </div>
      )}

      {isEvaluating && (
        <div className="flex items-center gap-3 rounded-md bg-primary-soft px-4 py-3 text-[13px] font-medium text-primary">
          <Spinner /> Grading your answers… results appear automatically.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {(selectedAssignment?.questions || []).map((quest, idx) => {
          const picked = isSubmitted ? quest.user_answer : answers[quest.id];
          return (
            <div
              key={quest.id}
              className={`flex flex-col gap-2.5 rounded-md border bg-surface p-4 shadow-sm ${isSubmitted ? (quest.is_correct ? 'border-accent/40' : 'border-danger/40') : 'border-line'}`}
            >
              <div className="text-sm font-medium text-ink"><strong>Q{idx + 1}.</strong> {quest.question_text}</div>
              <div className="flex flex-col gap-2">
                {(quest.options || []).map((opt) => {
                  const isPicked = picked === opt;
                  const isAnswer = isSubmitted && quest.correct_answer === opt;
                  return (
                    <button
                      key={opt}
                      type="button"
                      disabled={isSubmitted || isEvaluating || status === 'loading'}
                      onClick={() => selectOption(quest.id, opt)}
                      aria-pressed={isPicked}
                      className={`flex items-center gap-2.5 rounded-md border bg-surface px-3 py-2.5 text-left text-sm text-ink disabled:cursor-default ${
                        isAnswer
                          ? 'border-accent bg-accent-soft'
                          : isSubmitted && isPicked && !quest.is_correct
                            ? 'border-danger bg-danger-soft'
                            : isPicked
                              ? 'border-primary bg-primary-soft'
                              : 'border-line hover:border-primary'
                      }`}
                    >
                      <span className={`h-[18px] w-[18px] shrink-0 rounded-full border-2 ${
                        isAnswer ? 'border-accent bg-accent shadow-[inset_0_0_0_3px_#fff]'
                        : isPicked ? 'border-primary bg-primary shadow-[inset_0_0_0_3px_#fff]'
                        : 'border-line'
                      }`} />
                      <span className="min-w-0 flex-1">{opt}</span>
                      {isSubmitted && isAnswer && (
                        <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">Correct</span>
                      )}
                      {isSubmitted && isPicked && !quest.is_correct && (
                        <span className="shrink-0 rounded-full bg-danger px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">Your pick</span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {detailStatus === 'failed' && (
        <div className="error-banner">Question generation failed. Please go back and create a new assignment.</div>
      )}

      <ConfirmModal
        open={confirmSubmit}
        title="Submit assignment?"
        message={unansweredCount > 0
          ? `${unansweredCount} question(s) are still unanswered. Submit anyway? You cannot change answers after submitting.`
          : 'Submit the assignment for evaluation? You cannot change answers after submitting.'}
        confirmLabel="Submit"
        onConfirm={doSubmit}
        onCancel={() => setConfirmSubmit(false)}
      />
    </div>
  );
}
