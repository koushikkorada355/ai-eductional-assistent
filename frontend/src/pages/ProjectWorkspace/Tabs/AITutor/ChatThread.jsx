import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { IconChat, IconArrowRight, IconCheck } from '../../../../components/icons/Icons.jsx';
import QuickActions from './QuickActions.jsx';

// Matches every marker variant the model may emit:
// [Source: Page 3], [Sources: Pages 2, 3], [Source pp. 2-4], any casing.
const CITATION_MARKER_RE = /\[\s*sources?\s*:?\s*(?:pages?|pps?\.?|p\.?)?\s*[0-9][0-9\s,;.&\-–—]*\s*\]/gi;

export function stripCitations(text) {
  // Remove marker text only; then tidy spacing left behind without touching
  // code-block indentation (only collapse spaces on the marker's own line).
  return String(text || '')
    .replace(CITATION_MARKER_RE, '')
    .replace(/[ \t]+([.,;:!?)\]])/g, '$1')
    .replace(/([(\[])[ \t]+/g, '$1')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

/* Single-card flashcard viewer: click reveals the answer, Next advances,
 * finishing the deck ends the session. Raw Q/A markdown stays in the
 * message as the reload fallback. */
function FlashcardDeck({ cards }) {
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [finished, setFinished] = useState(false);
  useEffect(() => {
    setIndex(0);
    setFlipped(false);
    setFinished(false);
  }, [cards]);
  if (!Array.isArray(cards) || cards.length === 0) return null;
  if (finished) {
    return (
      <div className="flex w-full flex-col items-center gap-2 rounded-lg border border-line bg-surface p-5 text-center shadow-sm" aria-label="Flashcards complete">
        <span className="font-display text-sm font-semibold text-heading">
          You reviewed all {cards.length} flashcards
        </span>
        <span className="text-xs text-muted">Nice work. Want another pass?</span>
        <button
          type="button"
          onClick={() => { setIndex(0); setFlipped(false); setFinished(false); }}
          className="mt-1 inline-flex min-h-[30px] items-center rounded-full border border-line bg-surface px-3 text-xs font-medium text-ink transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary"
        >
          Review again
        </button>
      </div>
    );
  }
  const card = cards[Math.min(index, cards.length - 1)];
  const last = index >= cards.length - 1;
  return (
    <div className="flex w-full flex-col gap-2" aria-label={`Flashcard ${index + 1} of ${cards.length}`}>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted">
          Card {index + 1} of {cards.length}
        </span>
        <div className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${((index + 1) / cards.length) * 100}%` }}
          />
        </div>
      </div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => setFlipped((f) => !f)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setFlipped((f) => !f);
          }
        }}
        aria-label={flipped ? 'Hide answer, show question' : 'Reveal answer'}
        className={`cursor-pointer rounded-lg border p-4 shadow-sm transition-colors [perspective:1200px] focus-visible:outline-2 focus-visible:outline-primary ${
          flipped
            ? 'border-primary bg-primary-soft hover:border-primary-dark'
            : 'border-line bg-surface hover:border-primary'
        }`}
      >
        <motion.div
          animate={{ rotateY: flipped ? 180 : 0 }}
          transition={{ duration: 0.45, ease: [0.4, 0.1, 0.2, 1] }}
          style={{ transformStyle: 'preserve-3d' }}
          className="grid min-h-[120px]"
        >
          <div className="col-start-1 row-start-1 flex flex-col justify-center gap-1.5 [backface-visibility:hidden]">
            <span className="text-[10px] font-bold uppercase tracking-[0.06em] text-muted">
              Question — tap for answer
            </span>
            <div className="md-flash text-sm leading-relaxed text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {stripCitations(card.question)}
              </ReactMarkdown>
            </div>
          </div>
          <div className="col-start-1 row-start-1 flex flex-col justify-center gap-1.5 [backface-visibility:hidden] [transform:rotateY(180deg)]">
            <span className="text-[10px] font-bold uppercase tracking-[0.06em] text-primary">
              Answer — tap for question
            </span>
            <div className="md-flash text-sm leading-relaxed text-ink">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {stripCitations(card.answer)}
              </ReactMarkdown>
            </div>
          </div>
        </motion.div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setFlipped((f) => !f)}
          className="inline-flex min-h-[30px] items-center rounded-full border border-line bg-surface px-3 text-xs font-medium text-ink transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary"
        >
          {flipped ? 'Hide answer' : 'Reveal answer'}
        </button>
        <button
          type="button"
          onClick={() => {
            if (last) {
              setFinished(true);
            } else {
              setIndex((i) => i + 1);
              setFlipped(false);
            }
          }}
          className="inline-flex min-h-[30px] items-center gap-1.5 rounded-full bg-primary px-4 text-xs font-semibold text-white transition-colors hover:bg-primary-dark [&>svg]:h-3.5 [&>svg]:w-3.5"
        >
          {last ? 'Finish' : 'Next'} <IconArrowRight size={14} />
        </button>
      </div>
    </div>
  );
}

/* Practice MCQ deck: interactive multiple-choice drill rendered inline in
 * the chat. Answers are checked client-side only — nothing is written to
 * quiz tables and mastery is never touched. Raw markdown stays in the
 * message as the reload fallback. */
const MCQ_LETTERS = ['A', 'B', 'C', 'D'];

function McqDeck({ cards }) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState(null);
  const [checked, setChecked] = useState(false);
  const [results, setResults] = useState([]);
  const [finished, setFinished] = useState(false);
  useEffect(() => {
    setIndex(0);
    setPicked(null);
    setChecked(false);
    setResults([]);
    setFinished(false);
  }, [cards]);
  if (!Array.isArray(cards) || cards.length === 0) return null;
  const total = cards.length;
  const correctCount = results.filter(Boolean).length;

  if (finished) {
    const pct = Math.round((correctCount / total) * 100);
    return (
      <div className="flex w-full flex-col items-center gap-2 rounded-lg border border-line bg-surface p-5 text-center shadow-sm" aria-label="Practice complete">
        <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft font-display text-base font-bold text-primary">
          {pct}%
        </span>
        <span className="font-display text-sm font-semibold text-heading">
          You got {correctCount} of {total} right
        </span>
        <span className="text-xs text-muted">
          {pct === 100 ? 'Flawless — nicely done.' : pct >= 60 ? 'Solid. Retry to lock it in.' : 'Good effort — review the explanations and retry.'}
        </span>
        <button
          type="button"
          onClick={() => { setIndex(0); setPicked(null); setChecked(false); setResults([]); setFinished(false); }}
          className="mt-1 inline-flex min-h-[30px] items-center rounded-full border border-line bg-surface px-3 text-xs font-medium text-ink transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary"
        >
          Retry practice
        </button>
      </div>
    );
  }

  const card = cards[Math.min(index, total - 1)];
  const last = index >= total - 1;
  const answerIdx = Number(card.answer_index);
  const optionClass = (i) => {
    const base = 'flex w-full items-center gap-2.5 rounded-lg border px-3.5 py-2.5 text-left text-[13px] transition-colors';
    if (!checked) {
      return `${base} ${picked === i
        ? 'border-primary bg-primary-soft font-medium text-primary'
        : 'border-line bg-surface text-ink hover:border-primary hover:bg-primary-soft hover:text-primary'}`;
    }
    if (i === answerIdx) return `${base} border-green-600 bg-green-50 font-medium text-green-800`;
    if (i === picked) return `${base} border-red-500 bg-red-50 font-medium text-red-700`;
    return `${base} border-line bg-surface text-muted opacity-60`;
  };

  return (
    <div className="flex w-full flex-col gap-2.5" aria-label={`Practice question ${index + 1} of ${total}`}>
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted">
          Practice · {index + 1} of {total}
        </span>
        <div className="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas" aria-hidden="true">
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-300"
            style={{ width: `${((index + 1) / total) * 100}%` }}
          />
        </div>
        {results.length > 0 && (
          <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary-soft px-1.5 text-[11px] font-bold text-primary" aria-label={`${correctCount} correct so far`}>
            {correctCount} ✓
          </span>
        )}
      </div>
      <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
        <p className="text-sm font-medium leading-relaxed text-heading">{card.question}</p>
        <div className="mt-3 flex flex-col gap-1.5" role="group" aria-label="Answer options">
          {(card.options || []).slice(0, 4).map((opt, i) => (
            <button
              key={i}
              type="button"
              disabled={checked}
              onClick={() => setPicked(i)}
              aria-pressed={picked === i}
              aria-label={`Option ${MCQ_LETTERS[i]}: ${opt}`}
              className={optionClass(i)}
            >
              <span className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-bold ${
                checked && i === answerIdx
                  ? 'border-green-600 bg-green-600 text-white'
                  : checked && i === picked
                    ? 'border-red-500 bg-red-500 text-white'
                    : picked === i
                      ? 'border-primary bg-primary text-white'
                      : 'border-line bg-canvas text-muted'
              }`} aria-hidden="true">
                {checked && i === answerIdx ? <IconCheck size={13} /> : MCQ_LETTERS[i]}
              </span>
              <span className="min-w-0 flex-1">{opt}</span>
            </button>
          ))}
        </div>
        {checked && card.explanation && (
          <motion.p
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-3 rounded-md bg-canvas px-3 py-2 text-xs leading-relaxed text-ink"
          >
            <strong className={picked === answerIdx ? 'text-green-800' : 'text-red-700'}>
              {picked === answerIdx ? 'Correct. ' : 'Not quite. '}
            </strong>
            {card.explanation}
          </motion.p>
        )}
        <div className="mt-3 flex items-center justify-end gap-2">
          {!checked ? (
            <button
              type="button"
              disabled={picked == null}
              onClick={() => setChecked(true)}
              className="inline-flex min-h-[30px] items-center rounded-full bg-primary px-4 text-xs font-semibold text-white transition-colors hover:bg-primary-dark disabled:opacity-50"
            >
              Check answer
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                const next = [...results, picked === answerIdx];
                setResults(next);
                if (last) {
                  setFinished(true);
                } else {
                  setIndex((v) => v + 1);
                  setPicked(null);
                  setChecked(false);
                }
              }}
              className="inline-flex min-h-[30px] items-center gap-1.5 rounded-full bg-primary px-4 text-xs font-semibold text-white transition-colors hover:bg-primary-dark [&>svg]:h-3.5 [&>svg]:w-3.5"
            >
              {last ? 'See results' : 'Next'} <IconArrowRight size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* Follow-up recommendations: clickable chips rendered under each AI
 * response. Clicking sends the question as a new tutor turn. */
function SuggestedQuestions({ questions, disabled, onPick }) {
  if (!Array.isArray(questions) || questions.length === 0) return null;
  return (
    <motion.div
      className="tutor-suggestions"
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: 0.1 }}
      aria-label="Suggested follow-up questions"
    >
      <div className="tutor-suggestions-label" aria-hidden="true">
        <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M8 1.5 9.7 5.6 14 6.2 10.9 9.1 11.7 13.4 8 11.3 4.3 13.4 5.1 9.1 2 6.2 6.3 5.6 8 1.5Z"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinejoin="round"
          />
        </svg>
        <span>Keep exploring</span>
      </div>
      <div className="tutor-suggestions-list">
        {questions.map((quest, idx) => (
          <motion.button
            key={`${idx}-${quest}`}
            type="button"
            onClick={() => onPick?.(quest)}
            disabled={disabled}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22, delay: 0.14 + idx * 0.06 }}
            className="tutor-suggestion-chip"
            aria-label={`Ask: ${quest}`}
          >
            <span className="tutor-suggestion-text">{quest}</span>
            <span className="tutor-suggestion-arrow" aria-hidden="true">
              <IconArrowRight size={14} />
            </span>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
}

export default function ChatThread({
  messages, sending, loading, onSend,
  qaDisabled, qaPendingId, qaConversationId, onQuickAction,
  actionError, onDismissActionError,
}) {
  const [q, setQ] = useState('');
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages?.length, sending]);

  const submit = (e) => {
    e.preventDefault();
    const text = q.trim();
    if (!text || sending) return;
    setQ('');
    onSend(text);
    inputRef.current?.focus();
  };

  const sendSuggestion = (text) => {
    if (sending) return;
    onSend(text);
    inputRef.current?.focus();
  };

  const empty = !loading && (messages || []).length === 0;

  return (
    <>
      <div
        className="min-h-[320px] flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:min-h-0 lg:px-10"
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label="Conversation messages"
      >
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-5">
          {loading && (messages || []).length === 0 && (
            <div className="m-auto px-6 py-10 text-center">
              <p className="text-sm text-muted">Loading messages…</p>
            </div>
          )}
          {empty && (
            <div className="m-auto flex max-w-xl flex-col items-center gap-2 px-6 py-10 text-center">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary-soft text-primary [&>svg]:h-11 [&>svg]:w-11">
                <IconChat size={44} />
              </div>
              <h4 className="font-display text-lg font-semibold text-heading">
                Start a new learning conversation
              </h4>
              <p className="max-w-[420px] text-[13px] text-muted">
                Ask your AI Tutor about anything related to this project. Answers come strictly
                from your uploaded documents, with page citations. Use the Practice button below
                for a quick MCQ drill on what you have been discussing.
              </p>
            </div>
          )}
          <AnimatePresence initial={false}>
            {(messages || []).map((m, i) => (
              <motion.div
                key={m.id || i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22 }}
                className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
              >
                {m.role === 'assistant' ? (
                  <div className="min-w-0 max-w-full flex-1">
                    <div className="md-assistant text-sm leading-relaxed text-ink">
                      {Array.isArray(m.flashcards) && m.flashcards.length > 0 ? (
                        <FlashcardDeck cards={m.flashcards} />
                      ) : Array.isArray(m.mcq) && m.mcq.length > 0 ? (
                        <McqDeck cards={m.mcq} />
                      ) : (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {stripCitations(m.content)}
                        </ReactMarkdown>
                      )}
                    </div>
                    <SuggestedQuestions
                      questions={m.suggested_questions}
                      disabled={sending}
                      onPick={(quest) => {
                        if (sending) return;
                        sendSuggestion(quest);
                      }}
                    />
                  </div>
                ) : (
                  <div className="max-w-[80%] break-words rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-white">
                    {m.content}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {sending && (
            <motion.div
              className="flex items-center gap-1.5 py-2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              aria-label="AI is thinking"
            >
              <span className="dot" /><span className="dot" /><span className="dot" />
            </motion.div>
          )}
        </div>
      </div>
      <div className="shrink-0 border-t border-line bg-surface px-4 pb-3 pt-3 sm:px-6 lg:px-10">
        {onQuickAction && (
          <div className="mx-auto mb-2.5 w-full max-w-5xl">
            <QuickActions
              bare
              disabled={qaDisabled}
              pendingId={qaPendingId}
              conversationId={qaConversationId}
              onAction={onQuickAction}
            />
            {actionError && (
              <p className="mt-1.5 text-xs text-danger" role="alert">
                {actionError}{' '}
                <button type="button" className="font-semibold underline" onClick={onDismissActionError}>
                  Dismiss
                </button>
              </p>
            )}
          </div>
        )}
        <form
          onSubmit={submit}
          className="mx-auto flex w-full max-w-5xl gap-2 rounded-xl border border-line bg-surface p-2 shadow-sm transition-colors focus-within:border-primary"
        >
          <label htmlFor="tutor-composer" className="sr-only">Ask your AI Tutor</label>
          <input
            id="tutor-composer"
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask a question about your materials..."
            autoComplete="off"
            className="min-h-[40px] min-w-0 flex-1 rounded-lg border-0 bg-canvas px-3.5 text-sm focus:bg-surface focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <motion.button
            type="submit"
            whileTap={{ scale: 0.96 }}
            disabled={sending || !q.trim()}
            className="inline-flex min-h-[40px] shrink-0 items-center gap-1.5 rounded-lg bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50 [&>svg]:h-[18px] [&>svg]:w-[18px]"
          >
            Send <IconArrowRight size={18} />
          </motion.button>
        </form>
        <p className="mx-auto mt-1.5 w-full max-w-5xl text-[11px] text-muted">
          Answers are grounded in your uploaded documents. Always verify important claims.
        </p>
      </div>
    </>
  );
}
