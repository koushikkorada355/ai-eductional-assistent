import React, { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { loadAssignments, createAssignmentThunk, loadAssignment, submitAssignmentThunk, clearSelected } from '../../../../features/assignments/assignmentsSlice.js';
import { loadConcepts } from '../../../../features/concepts/conceptsSlice.js';
import './Assignments.css';

export default function Assignments({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { assignments, selectedAssignment, status, error } = useSelector((s) => s.assignments);
  const { concepts } = useSelector((s) => s.concepts);

  const [view, setView] = useState('list');
  const [selectedConcepts, setSelectedConcepts] = useState([]);
  const [title, setTitle] = useState('');
  const [numQuestions, setNumQuestions] = useState(5);
  const [answers, setAnswers] = useState({});

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
    try {
      await dispatch(createAssignmentThunk({
        spaceId,
        projectId,
        conceptIds: selectedConcepts,
        numQuestions,
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
    if (unanswered.length > 0 && !window.confirm(`${unanswered.length} question(s) unanswered. Submit anyway?`)) {
      return;
    }
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

  return (
    <div className="assignments-container">
      <AnimatePresence mode="wait">
        {view === 'list' && (
          <motion.div
            key="list"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="assignments-list"
          >
            <h2>Your Assignments</h2>
            <button className="btn-new" onClick={() => setView('create')}>+ New Assignment</button>
            {error && <div className="error-banner">{error}</div>}
            <div className="assignments-grid">
              {assignments.map((a) => (
                <div key={a.id} className="assignment-card" onClick={() => handleView(a)}>
                  <div className="card-header">
                    <h3>{a.title || 'Assignment'}</h3>
                    <span className={`status ${a.status}`}>{a.status}</span>
                  </div>
                  <div className="card-meta">
                    <span>{a.num_questions ?? 0} MCQ(s)</span>
                    {a.status === 'submitted' && a.total != null && (
                      <span className={`score-badge ${a.score === a.total ? 'perfect' : a.score / a.total >= 0.5 ? 'pass' : 'fail'}`}>
                        Score: {a.score}/{a.total}
                      </span>
                    )}
                  </div>
                  <div className="card-footer">
                    <span className="created">{a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</span>
                  </div>
                </div>
              ))}
              {assignments.length === 0 && (
                <div className="empty-state">
                  <p>No assignments yet. Create one to test your understanding!</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {view === 'create' && (
          <motion.div
            key="create"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="assignments-create"
          >
            <h2>Create New Assignment</h2>
            <p>Generates multiple MCQ questions from your concepts, grounded in your materials.</p>
            {error && <div className="error-banner">{error}</div>}

            <div className="create-section">
              <h3>Step 1: Select Concepts</h3>
              <p>Select one or more concepts to base the MCQs on.</p>
              <button
                className="concept-select"
                onClick={() => setView('select-concepts')}
              >
                {selectedConcepts.length > 0 ? `${selectedConcepts.length} concept(s) selected` : 'Select concepts...'}
              </button>
            </div>

            <div className="create-section">
              <h3>Step 2: Title (Optional)</h3>
              <input
                className="title-input"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g., Photosynthesis Practice Set"
                maxLength={200}
              />
            </div>

            <div className="create-section">
              <h3>Step 3: Number of Questions</h3>
              <div className="num-row">
                {[3, 5, 8, 10].map((n) => (
                  <button
                    key={n}
                    className={`num-btn ${numQuestions === n ? 'active' : ''}`}
                    onClick={() => setNumQuestions(n)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            <div className="create-actions">
              <button className="btn-back" onClick={() => setView('list')}>Back</button>
              <button
                className="btn-create"
                disabled={selectedConcepts.length === 0 || status === 'loading'}
                onClick={handleCreate}
              >
                {status === 'loading' ? 'Generating MCQs...' : `Generate ${numQuestions} MCQs`}
              </button>
            </div>
          </motion.div>
        )}

        {view === 'select-concepts' && (
          <motion.div
            key="select-concepts"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="assignments-create"
          >
            <h2>Select Concepts</h2>
            <p>Click to select/deselect concepts.</p>

            <div className="concept-list">
              {(concepts || []).length === 0 ? (
                <p className="empty-state">No concepts found. Upload a PDF to generate concepts first.</p>
              ) : (
                (concepts || []).map((c) => {
                  const score = Math.round(c.mastery_level || 0);
                  return (
                    <label key={c.id} className="concept-item">
                      <input
                        type="checkbox"
                        checked={selectedConcepts.includes(c.id)}
                        onChange={() => toggleConcept(c.id)}
                      />
                      <span className="concept-body">
                        <span className="concept-name">{c.name}</span>
                        {c.description && <span className="concept-desc">{c.description}</span>}
                        <span className="concept-mastery">
                          <span className="mastery-mini-track">
                            <span
                              className={`mastery-mini-fill ${score >= 70 ? 'strong' : score >= 40 ? 'learning' : 'weak'}`}
                              style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                            />
                          </span>
                          <span className="mastery-mini-label">{score}% mastery</span>
                        </span>
                      </span>
                    </label>
                  );
                })
              )}
            </div>

            <div className="create-actions">
              <button className="btn-back" onClick={() => setView('create')}>Cancel</button>
              <button className="btn-create" onClick={() => setView('create')}>Done</button>
            </div>
          </motion.div>
        )}

        {view === 'view' && selectedAssignment && (
          <motion.div
            key="view"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="assignments-view"
          >
            <div className="view-header">
              <button className="btn-back" onClick={handleBack}>← Back to Assignments</button>
              <span className={`status ${selectedAssignment.status}`}>{selectedAssignment.status}</span>
            </div>

            <h2>{selectedAssignment.title || 'Assignment'}</h2>

            {error && <div className="error-banner">{error}</div>}

            {isSubmitted && selectedAssignment.total != null && (
              <div className={`score-banner ${selectedAssignment.score === selectedAssignment.total ? 'perfect' : selectedAssignment.score / selectedAssignment.total >= 0.5 ? 'pass' : 'fail'}`}>
                <strong>Score: {selectedAssignment.score}/{selectedAssignment.total}</strong>
                {selectedAssignment.feedback?.overall && <p>{selectedAssignment.feedback.overall}</p>}
              </div>
            )}

            {isEvaluating && (
              <div className="grading-banner">
                <span className="spinner" />
                <span>Grading your answers… results appear automatically.</span>
              </div>
            )}

            {!isSubmitted && !isEvaluating && totalCount > 0 && (
              <div className="progress-line">
                Answered {answeredCount}/{totalCount}
                <div className="progress-bar"><div className="progress-fill" style={{ width: `${(answeredCount / totalCount) * 100}%` }} /></div>
              </div>
            )}

            <div className="mcq-list">
              {(selectedAssignment.questions || []).map((q, idx) => {
                const picked = isSubmitted ? q.user_answer : answers[q.id];
                return (
                  <div key={q.id} className={`mcq-card ${isSubmitted ? (q.is_correct ? 'correct' : 'wrong') : ''}`}>
                    <div className="mcq-q"><strong>Q{idx + 1}.</strong> {q.question_text}</div>
                    <div className="mcq-options">
                      {(q.options || []).map((opt) => {
                        const isPicked = picked === opt;
                        const isAnswer = isSubmitted && q.correct_answer === opt;
                        return (
                          <button
                            key={opt}
                            disabled={isSubmitted || isEvaluating || status === 'loading'}
                            className={`mcq-opt ${isPicked ? 'picked' : ''} ${isAnswer ? 'answer' : ''} ${isSubmitted && isPicked && !q.is_correct ? 'wrong-pick' : ''}`}
                            onClick={() => selectOption(q.id, opt)}
                          >
                            <span className="opt-radio" />
                            <span>{opt}</span>
                            {isSubmitted && isAnswer && <span className="opt-mark ok">Correct</span>}
                            {isSubmitted && isPicked && !q.is_correct && <span className="opt-mark bad">Your pick</span>}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>

            {isReady && (
              <button className="btn-submit" onClick={handleSubmit} disabled={status === 'loading' || totalCount === 0}>
                {status === 'loading' ? 'Submitting...' : `Submit Assignment (${answeredCount}/${totalCount})`}
              </button>
            )}
            {detailStatus === 'failed' && (
              <div className="error-banner">Question generation failed. Please go back and create a new assignment.</div>
            )}
          </motion.div>
        )}

        {view === 'generating' && (
          <motion.div
            key="generating"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="assignments-create generating-card"
          >
            {selectedAssignment?.status === 'failed' ? (
              <>
                <h2>Generation failed</h2>
                <p>The graph could not generate questions for this assignment.</p>
                <div className="create-actions">
                  <button className="btn-back" onClick={handleBack}>Back to Assignments</button>
                </div>
              </>
            ) : (
              <>
                <h2>Building “{selectedAssignment?.title || 'your assignment'}”</h2>
                <p>Reading your materials and crafting MCQs in the background. This takes a moment...</p>
                <div className="generating-spinner"><span className="spinner" /></div>
                <div className="create-actions">
                  <button className="btn-back" onClick={handleBack}>Back to Assignments</button>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
