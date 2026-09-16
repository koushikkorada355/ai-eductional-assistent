import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { sendQuestion, loadMessages, pushUser } from '../../../../features/tutor/tutorSlice.js';
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
        {messages.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            {m.role === 'assistant' ? renderWithCitations(m.content) : m.content}
          </div>
        ))}
        {status === 'loading' && <div className="bubble assistant">Thinking...</div>}
      </div>
      <form className="chat-input" onSubmit={send}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask about this project's materials..." />
        <button type="submit">Send</button>
      </form>
    </div>
  );
}
