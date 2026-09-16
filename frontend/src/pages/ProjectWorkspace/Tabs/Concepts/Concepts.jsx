import React, { useEffect, useMemo } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion } from 'framer-motion';
import { loadConcepts } from '../../../../features/concepts/conceptsSlice.js';
import './Concepts.css';

function levelOf(score) {
  if (score >= 70) return { label: 'Strong', cls: 'strong' };
  if (score >= 40) return { label: 'Learning', cls: 'learning' };
  return { label: 'Needs work', cls: 'weak' };
}

export default function Concepts({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { concepts, status, error } = useSelector((s) => s.concepts);

  useEffect(() => {
    if (spaceId && projectId) {
      dispatch(loadConcepts({ spaceId, projectId }));
    }
  }, [dispatch, spaceId, projectId]);

  const sorted = useMemo(
    () => [...(concepts || [])].sort((a, b) => (a.mastery_level || 0) - (b.mastery_level || 0)),
    [concepts]
  );

  const avg = useMemo(() => {
    if (!concepts || concepts.length === 0) return 0;
    return concepts.reduce((s, c) => s + (c.mastery_level || 0), 0) / concepts.length;
  }, [concepts]);

  const weakest = sorted[0];

  return (
    <div className="concepts-container">
      <div className="concepts-header">
        <div>
          <h2>Project Concepts</h2>
          <p className="muted">
            Extracted from your materials. Mastery updates automatically when you submit quizzes and assignments.
          </p>
        </div>
        <button
          className="btn-back"
          onClick={() => dispatch(loadConcepts({ spaceId, projectId }))}
          disabled={status === 'loading'}
        >
          {status === 'loading' ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {concepts && concepts.length > 0 && (
        <div className="concepts-stats">
          <div className="stat-card">
            <span className="stat-value">{concepts.length}</span>
            <span className="stat-label">Concepts</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{Math.round(avg)}%</span>
            <span className="stat-label">Avg mastery</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{weakest ? weakest.name : '—'}</span>
            <span className="stat-label">Weakest concept</span>
          </div>
        </div>
      )}

      {status === 'loading' && (!concepts || concepts.length === 0) && (
        <p className="muted">Loading concepts...</p>
      )}

      {status !== 'loading' && (!concepts || concepts.length === 0) && !error && (
        <div className="empty-state">
          <p>No concepts yet. Upload a PDF in Materials to generate concepts for this project.</p>
        </div>
      )}

      <div className="concepts-grid">
        {sorted.map((c, i) => {
          const score = Math.round(c.mastery_level || 0);
          const level = levelOf(score);
          return (
            <motion.div
              key={c.id}
              className="concept-card"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.04, 0.4) }}
            >
              <div className="concept-card-top">
                <h3>{c.name}</h3>
                <span className={`level-badge ${level.cls}`}>{level.label}</span>
              </div>
              {c.description && <p className="concept-card-desc">{c.description}</p>}
              <div className="mastery-label">
                <span>Mastery</span>
                <span>{score}%</span>
              </div>
              <div className="mastery-track">
                <motion.div
                  className={`mastery-fill ${level.cls}`}
                  animate={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                  transition={{ duration: 0.6 }}
                />
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
