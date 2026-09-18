import {
  IconFile, IconTarget, IconClipboard, IconSpark, IconGraduation,
} from '../../../../components/icons/Icons.jsx';

/* Placeholders shown as the user message for generation turns: creative
 * status text with no topic in it. Topic helpers skip them so later actions
 * still key off the learner's real last question. */
export const PRACTICE_PLACEHOLDER = 'Generating practice questions…';
export const FLASHCARDS_PLACEHOLDER = 'Generating flashcards…';
export const SUMMARY_PLACEHOLDER = 'Generating summary…';
export const DEEPDIVE_PLACEHOLDER = 'Generating deep dive…';
const PLACEHOLDER_BUBBLES = [
  PRACTICE_PLACEHOLDER, FLASHCARDS_PLACEHOLDER,
  SUMMARY_PLACEHOLDER, DEEPDIVE_PLACEHOLDER,
];

/* The five tutor Quick Actions. Content actions flow through the normal
 * tutor-turn pipeline (see tutorSlice.sendQuestion + backend app.ai.actions);
 * generate_quiz reuses the existing quiz-start flow instead. Practice renders
 * MCQs inline in the chat and never touches mastery. */
export const QUICK_ACTIONS = [
  {
    id: 'summarize',
    label: 'Summarize',
    Icon: IconFile,
    // Creative placeholder bubble — never echoes the questions. The summary
    // is built from conversation memory on the backend, not this text.
    buildPrompt: () => SUMMARY_PLACEHOLDER,
  },
  {
    id: 'deep_dive',
    label: 'Deep Dive',
    Icon: IconTarget,
    // Creative placeholder bubble — never echoes the questions. The deep
    // dive is built from conversation memory on the backend, not this text.
    buildPrompt: () => DEEPDIVE_PLACEHOLDER,
  },
  {
    id: 'generate_quiz',
    label: 'Generate Quiz',
    Icon: IconClipboard,
    isQuiz: true,
  },
  {
    id: 'create_flashcards',
    label: 'Create Flashcards',
    Icon: IconSpark,
    // Creative placeholder bubble — the real question is never shown and no
    // topic is mentioned. Cards are generated from the retrieved materials
    // for the recent discussion topic, not this text.
    buildPrompt: () => FLASHCARDS_PLACEHOLDER,
  },
  {
    id: 'practice',
    label: 'Practice',
    Icon: IconGraduation,
    // Creative placeholder bubble — the real question is never shown and no
    // topic is mentioned. The backend practice directive builds the MCQs
    // from the conversation history, not this text.
    buildPrompt: () => PRACTICE_PLACEHOLDER,
  },
];

/* Known quick-action wrappers. Stripped (repeatedly) so chained actions
 * resolve back to the learner's original topic instead of compounding.
 * The 'explain clearly:' prefix is retained for history written before
 * the Explain This action was removed. */
const ACTION_PREFIXES = [
  'explain clearly:',
  'summarize concisely:',
  'give me a detailed deep dive on',
  'generate an adaptive quiz on:',
  'generate a quiz on:',
  'create study flashcards covering:',
  'quiz me with practice mcqs on:',
];
const ACTION_SUFFIX = ', including important details, relationships, and examples';

export function cleanTopic(raw) {
  let t = String(raw || '').trim().replace(/\s+/g, ' ');
  for (let guard = 0; guard < 6 && t; guard += 1) {
    const lower = t.toLowerCase();
    const hit = ACTION_PREFIXES.find((p) => lower.startsWith(p));
    if (!hit) break;
    t = t.slice(hit.length).trim();
  }
  if (t.toLowerCase().endsWith(ACTION_SUFFIX)) {
    t = t.slice(0, t.length - ACTION_SUFFIX.length).trim();
  }
  return t;
}

/* Topic = most recent real user message (what the learner is actually on),
 * unwrapped from any previous quick-action phrasing, truncated; falls
 * back to the project's key concepts. Drill placeholder bubbles are skipped —
 * they carry no topic. */
export function lastRealUserText(activeMessages) {
  const lastUser = [...(activeMessages || [])].reverse().find((m) => {
    if (m?.role !== 'user') return false;
    const t = cleanTopic(m?.content);
    return Boolean(t) && !PLACEHOLDER_BUBBLES.includes(t);
  });
  return cleanTopic(lastUser?.content);
}

export function deriveActionTopic(activeMessages) {
  const text = lastRealUserText(activeMessages);
  if (text) return text.length > 200 ? `${text.slice(0, 200).trim()}…` : text;
  return 'the key concepts in my documents';
}

/* Greetings / small-talk only (hii, hello, thanks, ok …). Quick actions
 * that generate study material must not run on these — there is no topic.
 * Anchored full-match so real (even short) questions always pass through. */
const GENERAL_RE = /^(h+i+|hello+|hey+|yo|sup|thanks?|thank\s*you|thx|bye+|good\s?(morning|afternoon|evening|night)|o+k+|okay+|sure|yes+|no+|please+|help+|test+(ing)?|how\s+are\s+you(\s+doing)?)\W*$/i;

export function isGeneralMessage(text) {
  const t = String(text || '').trim().replace(/\s+/g, ' ');
  if (!t) return true;
  return GENERAL_RE.test(t);
}

export function shortTopic(topic, max = 48) {
  const t = String(topic || '').trim();
  if (t.length <= max) return t;
  const cut = t.slice(0, max).trim();
  const sp = cut.lastIndexOf(' ');
  return `${sp > 10 ? cut.slice(0, sp) : cut}…`;
}

/* Compact, secondary strip: five small buttons, never competing with chat.
 * Renders as a labeled strip by default, or bare (row only) when embedded
 * e.g. above the composer via the `bare` prop. */
export default function QuickActions({ disabled, pendingId, conversationId, onAction, bare }) {
  const row = (
    <div className="flex w-full flex-wrap items-center gap-1.5" role="group" aria-label="Quick actions">
        {QUICK_ACTIONS.map(({ id, label, Icon, isQuiz }) => {
          const pending = pendingId === id;
          const unavailable = !isQuiz && !conversationId;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onAction(id)}
              disabled={disabled || pending || unavailable}
              aria-label={label}
              title={unavailable ? `${label} (start a conversation first)` : label}
              className="inline-flex min-h-[30px] items-center gap-1.5 rounded-full border border-line bg-surface px-3 text-xs font-medium text-ink transition-colors hover:border-primary hover:bg-primary-soft hover:text-primary disabled:cursor-default disabled:opacity-50 [&>svg]:h-3.5 [&>svg]:w-3.5"
            >
              <Icon size={14} />
              {pending ? 'Working…' : label}
            </button>
          );
        })}
    </div>
  );
  if (bare) return row;
  return (
    <div className="shrink-0 border-b border-line bg-surface px-4 py-2 sm:px-6 lg:px-10">
      <div className="mx-auto w-full max-w-5xl">{row}</div>
    </div>
  );
}
