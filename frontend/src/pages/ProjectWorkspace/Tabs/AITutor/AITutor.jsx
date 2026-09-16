import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { sendQuestion, loadMessages, pushUser } from '../../../../features/tutor/tutorSlice.js';
import { IconChat, IconArrowRight } from '../../../../components/icons/Icons.jsx';
import './AITutor.css';

function renderWithCitations(text) {
  const parts = String(text || '').split(/(\[Source:\s*Page\s*\d+\])/g);
  return parts.map((p, i) =>
    /\[Source:\s*Page\s*\d+\]/.test(p)
      ? <span key={i} className="citation">{p}</span>
      : <span key={i}>{p}</span>
  );
}

export default function AITutor({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { messages, status } = useSelector((s) => s.tutor);
  const [q, setQ] = useState('');

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadMessages({ spaceId, projectId }));
  }, [dispatch, spaceId, projectId]);

  const send = async (e) => {
    e.preventDefault();
    if (!q.trim()) return;
    const text = q;
    setQ('');
    dispatch(pushUser(text));
    dispatch(sendQuestion({ spaceId, projectId, question: text }));
  };

  return (
    <div className="tutor">
      <div className="chat-list">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="chat-empty-icon"><IconChat size={44} /></div>
            <h4>Ask anything about your materials</h4>
            <p className="muted">Answers come strictly from your uploaded documents, with page citations.</p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {messages.map((m, i) => {
            const showSources = m.role === 'assistant' && m.citations && m.citations.length > 0;
            return (
              <motion.div
                key={i}
                className={showSources ? 'qa-row' : `bubble ${m.role}`}
                initial={{ opacity: 0, y: 10, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.22 }}
              >
                <div className={showSources ? 'bubble assistant' : undefined}>
                  {m.role === 'assistant' ? renderWithCitations(m.content) : m.content}
                </div>
                {showSources && (
                  <div className="sources-side">
                    <div className="sources-title">Sources</div>
                    {m.citations.map((c, j) => (
                      <div key={j} className="source-card">
                        <span className="source-doc">{c.pdf_name}</span>
                        <span className="source-page">Page {c.page_number}</span>
                        <p className="muted">{c.chunk_excerpt}</p>
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
        {status === 'loading' && (
          <motion.div className="bubble assistant thinking" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <span className="dot" /><span className="dot" /><span className="dot" />
          </motion.div>
        )}
      </div>
      <form className="chat-input" onSubmit={send}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about this project's materials..." />
        <motion.button type="submit" whileTap={{ scale: 0.96 }}>Send <IconArrowRight size={18} /></motion.button>
      </form>
    </div>
  );
}
