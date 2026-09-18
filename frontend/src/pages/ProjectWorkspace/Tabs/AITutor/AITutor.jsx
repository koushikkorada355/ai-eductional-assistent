import { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import {
  sendQuestion,
  pushUser,
  setActiveConversation,
  resetForProject,
  loadConversations,
  loadConversationMessages,
  newConversation,
  renameConversationThunk,
  removeConversation,
  normalizeCitations,
} from '../../../../features/tutor/tutorSlice.js';
import ConfirmModal from '../../../../components/ConfirmModal/ConfirmModal.jsx';
import { IconChat, IconFile } from '../../../../components/icons/Icons.jsx';
import ConversationSidebar from './ConversationSidebar.jsx';
import ChatThread from './ChatThread.jsx';
import SourcesPanel from './SourcesPanel.jsx';
import QuickActions, { QUICK_ACTIONS, deriveActionTopic, shortTopic, lastRealUserText, isGeneralMessage } from './QuickActions.jsx';
import { startQuiz } from '../../../../features/quiz/quizSlice.js';
import './AITutor.css';

function RenameModal({ open, initial, saving, error, onSave, onClose }) {
  const [value, setValue] = useState(initial || '');
  useEffect(() => {
    if (open) {
      setValue(initial || '');
    }
  }, [open, initial]);
  const trimmed = value.trim();
  const invalid = trimmed.length === 0 || trimmed.length > 200;
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="flex w-full max-w-md flex-col gap-3 rounded-card bg-surface p-6 shadow-lg"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Rename conversation"
          >
            <h3 className="font-display text-base font-semibold text-heading">Rename conversation</h3>
            <label htmlFor="convo-rename" className="sr-only">Conversation title</label>
            <input
              id="convo-rename"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              maxLength={200}
              placeholder="Conversation title"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !invalid && !saving) onSave(trimmed);
                if (e.key === 'Escape') onClose();
              }}
              className="min-h-[38px] w-full rounded-md border border-line bg-surface px-3 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            />
            {error && <p className="text-xs text-danger">{error}</p>}
            <div className="mt-2 flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => onSave(trimmed)}
                disabled={invalid || saving}
                className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default function AITutor({ spaceId, projectId, conversationId, onSelectConversation, onOpenQuiz }) {
  const dispatch = useDispatch();
  const tutor = useSelector((s) => s.tutor);
  const { documents } = useSelector((s) => s.spaceProject || {});
  const [navOpen, setNavOpen] = useState(false);
  // Docked sources only by default on very wide screens — below that the
  // panel becomes an overlay so the conversation keeps the available width.
  const [sourcesOpen, setSourcesOpen] = useState(
    () => typeof window === 'undefined' || window.innerWidth >= 1536
  );
  // Desktop collapse for the conversations panel (rail). Chat-first default:
  // the panel starts collapsed unless the user explicitly expanded it before.
  // Persisted per project.
  const [convoCollapsed, setConvoCollapsed] = useState(true);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameSaving, setRenameSaving] = useState(false);
  const [renameError, setRenameError] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const projectKey = `${spaceId}/${projectId}`;

  // Project isolation: wipe tutor state the moment the project changes.
  useEffect(() => {
    dispatch(resetForProject(projectKey));
  }, [dispatch, projectKey]);

  // Restore the per-project conversations-panel preference.
  useEffect(() => {
    try {
      setConvoCollapsed(localStorage.getItem(`tutor-convo:${projectKey}`) !== '0');
    } catch {
      setConvoCollapsed(true);
    }
  }, [projectKey]);

  const toggleConvo = () => {
    setConvoCollapsed((v) => {
      const next = !v;
      try {
        localStorage.setItem(`tutor-convo:${projectKey}`, next ? '1' : '0');
      } catch {
        // private mode etc. — collapse still works for the session
      }
      return next;
    });
  };

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadConversations({ spaceId, projectId }));
  }, [dispatch, spaceId, projectId]);

  const conversations = useMemo(() => tutor.conversations || [], [tutor.conversations]);
  const listLoaded = tutor.listStatus === 'succeeded' || tutor.listStatus === 'failed';

  // Deep link / back-forward: activate the conversation from the URL.
  useEffect(() => {
    if (!listLoaded) return;
    if (conversationId) {
      const exists = conversations.some((c) => c.id === conversationId);
      if (exists) {
        dispatch(setActiveConversation(conversationId));
      }
    } else if (conversations.length > 0 && !tutor.activeId) {
      // No conversation in URL: settle on the most recent one.
      onSelectConversation?.(conversations[0].id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [listLoaded, conversationId, conversations.length]);

  // Load history for the active conversation only (lightweight nav + one thread).
  useEffect(() => {
    if (!conversationId || !spaceId || !projectId) return;
    const exists = conversations.some((c) => c.id === conversationId);
    if (!exists && listLoaded) return;
    if (!tutor.loadedById[conversationId] && !tutor.loadingById[conversationId]) {
      dispatch(loadConversationMessages({ spaceId, projectId, conversationId }));
    }
  }, [dispatch, conversationId, spaceId, projectId, conversations, listLoaded, tutor.loadedById, tutor.loadingById]);

  const active = conversations.find((c) => c.id === conversationId) || null;
  const activeMessages = conversationId ? tutor.messagesById[conversationId] || [] : [];
  const sending = conversationId ? !!tutor.sendingById[conversationId] : false;
  const loadingMsgs = conversationId ? !!tutor.loadingById[conversationId] && !tutor.loadedById[conversationId] : false;
  const invalidId = listLoaded && conversationId && !active;
  const docCount = Array.isArray(documents) ? documents.length : 0;
  const latestAssistant = useMemo(
    () => [...activeMessages].reverse().find((m) => m.role === 'assistant') || null,
    [activeMessages]
  );
  const sourceCount = normalizeCitations(latestAssistant?.citations).length;

  const handleSelect = (id) => {
    dispatch(setActiveConversation(id));
    setNavOpen(false);
    onSelectConversation?.(id);
  };

  const handleNew = async () => {
    try {
      const created = await dispatch(newConversation({ spaceId, projectId })).unwrap();
      setNavOpen(false);
      onSelectConversation?.(created.id);
    } catch {
      // error already in slice state
    }
  };

  const handleSend = (text) => {
    if (!conversationId || !text.trim()) return;
    dispatch(pushUser({ conversationId, content: text }));
    dispatch(sendQuestion({ spaceId, projectId, conversationId, question: text }));
  };

  // Quick-action handler: content actions reuse the normal tutor turn
  // (question + action hint through the same RAG pipeline); generate_quiz
  // starts an adaptive quiz grounded in this conversation via the existing
  // quiz-start flow, then hands off to the Quiz tab.
  const [pendingAction, setPendingAction] = useState(null);
  const [actionError, setActionError] = useState(null);

  // Recent conversation turns, so the quiz adapts to what was discussed —
  // the quiz engine already adapts to mastery; this grounds it in topic too.
  const conversationContext = (activeMessages || [])
    .filter((m) => m.role === 'user')
    .slice(-3)
    .map((m) => String(m.content || '').trim().replace(/\s+/g, ' '))
    .filter(Boolean)
    .join(' | ')
    .slice(0, 500);

  const handleQuickAction = async (actionId) => {
    const def = QUICK_ACTIONS.find((a) => a.id === actionId);
    if (!def || sending) return;
    setActionError(null);
    const topic = deriveActionTopic(activeMessages);
    // Never generate study material from greetings / small-talk — there is
    // no topic to build on. Fresh conversations (no real question yet) are
    // still allowed through via the fallback topic.
    const realQ = lastRealUserText(activeMessages);
    if (realQ && isGeneralMessage(realQ)) {
      setActionError('Quick actions need a study topic — ask a question about your materials first.');
      return;
    }
    if (def.isQuiz) {
      const prompt = `Generate an adaptive quiz on: ${topic}`;
      setPendingAction(actionId);
      try {
        if (conversationId) dispatch(pushUser({ conversationId, content: prompt }));
        await dispatch(startQuiz({
          projectId,
          name: `Adaptive quiz: ${shortTopic(topic)}`,
          goal: conversationContext
            ? `Adaptive quiz based on our conversation. Recent discussion: ${conversationContext}`
            : `Adaptive quiz on: ${topic}`,
          numMcq: 3,
          numOpen: 2,
        })).unwrap();
        onOpenQuiz?.();
      } catch {
        setActionError('Could not generate the quiz. Please try again.');
      } finally {
        setPendingAction(null);
      }
      return;
    }
    if (!conversationId) return;
    const text = def.buildPrompt(topic);
    dispatch(pushUser({ conversationId, content: text }));
    dispatch(sendQuestion({ spaceId, projectId, conversationId, question: text, action: def.id }));
  };

  const handleRenameSave = async (title) => {
    if (!renameTarget) return;
    setRenameSaving(true);
    setRenameError(null);
    try {
      await dispatch(renameConversationThunk({
        spaceId, projectId, conversationId: renameTarget.id, title,
      })).unwrap();
      setRenameTarget(null);
    } catch {
      setRenameError('Could not rename. Please try again.');
    } finally {
      setRenameSaving(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    const wasActive = deleteTarget.id === conversationId;
    try {
      await dispatch(removeConversation({ spaceId, projectId, conversationId: deleteTarget.id })).unwrap();
      setDeleteTarget(null);
      if (wasActive) {
        // Reducer already picked the next conversation; navigate to it (or base when empty).
        const remaining = conversations.filter((c) => c.id !== deleteTarget.id);
        onSelectConversation?.(remaining.length ? remaining[0].id : null);
      }
    } catch {
      setDeleteTarget(null);
    }
  };

  const showThread = !invalidId && conversationId;

  return (
    <div className="flex min-h-[70vh] min-w-0 flex-1 flex-col gap-4 lg:h-[calc(100dvh-180px)] lg:min-h-[480px] lg:flex-row">
      {/* Unified tutor workspace: conversations live INSIDE this card as a
          flush secondary column — never a second app-level sidebar. */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-card border border-line bg-surface shadow-sm lg:flex-row">
      <ConversationSidebar
        conversations={conversations}
        activeId={conversationId}
        creating={tutor.createStatus === 'creating'}
        createError={tutor.createError}
        listLoading={tutor.listStatus === 'loading'}
        listError={tutor.listStatus === 'failed' ? (tutor.error || 'Failed to load conversations') : null}
        navOpen={navOpen}
        onCloseNav={() => setNavOpen(false)}
        onSelect={handleSelect}
        onNew={handleNew}
        onRetryList={() => dispatch(loadConversations({ spaceId, projectId }))}
        onRename={(c) => { setRenameError(null); setRenameTarget(c); }}
        onDelete={(c) => setDeleteTarget(c)}
        collapsed={convoCollapsed}
        onCollapse={() => toggleConvo()}
        onExpand={() => toggleConvo()}
      />

      {/* Main conversation column — the primary experience */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex shrink-0 items-center gap-2.5 border-b border-line px-4 py-2.5">
          <button
            type="button"
            onClick={() => setNavOpen(true)}
            aria-label="Open conversations"
            className="inline-flex items-center justify-center rounded-md bg-primary-soft p-[7px] text-primary lg:hidden"
          >
            <IconChat size={18} />
          </button>
          <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary font-display text-xs font-bold text-white">
            AI
          </span>
          <span className="flex min-w-0 flex-1 flex-col leading-snug">
            <span className="truncate font-display text-sm font-semibold text-heading">
              {active ? active.title : 'AI Tutor'}
            </span>
            <span className="text-[11px] text-muted">
              {docCount > 0 ? `${docCount} document${docCount === 1 ? '' : 's'}` : 'Grounded in your documents'}
            </span>
          </span>
          {/* Sources control. Conversations are toggled from the panel
              itself (collapse button) and the rail — no duplicate header
              toggle, so the chat header stays a single compact row. */}
          {showThread && (
            <button
              type="button"
              onClick={() => setSourcesOpen((v) => !v)}
              aria-expanded={sourcesOpen}
              className={`inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md border px-3 text-[13px] font-medium transition-colors ${
                sourcesOpen
                  ? 'border-primary bg-primary-soft text-primary'
                  : 'border-line bg-surface text-muted hover:border-primary hover:text-primary'
              } [&>svg]:h-4 [&>svg]:w-4`}
            >
              <IconFile size={16} />
              <span className="hidden sm:inline">Sources</span>
              {sourceCount > 0 && (
                <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 text-[11px] font-bold text-white">
                  {sourceCount}
                </span>
              )}
            </button>
          )}
        </div>

        {invalidId ? (
          <div className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="m-auto flex max-w-md flex-col items-center gap-2 text-center">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary-soft text-primary [&>svg]:h-11 [&>svg]:w-11">
                <IconChat size={44} />
              </div>
              <h4 className="font-display text-base font-semibold text-heading">Conversation not found</h4>
              <p className="text-[13px] text-muted">It may have been deleted or belong to another project.</p>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                {conversations.length > 0 && (
                  <button
                    type="button"
                    onClick={() => handleSelect(conversations[0].id)}
                    className="rounded-full border border-line bg-surface px-3.5 py-[7px] text-xs font-medium text-ink hover:border-primary hover:bg-primary-soft hover:text-primary"
                  >
                    Open most recent conversation
                  </button>
                )}
                <button
                  type="button"
                  onClick={handleNew}
                  className="rounded-full border border-line bg-surface px-3.5 py-[7px] text-xs font-medium text-ink hover:border-primary hover:bg-primary-soft hover:text-primary"
                >
                  Start a new conversation
                </button>
              </div>
            </div>
          </div>
        ) : !conversationId ? (
          <div className="flex flex-1 items-center justify-center px-6 py-10">
            <div className="m-auto flex max-w-md flex-col items-center gap-2 text-center">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-full bg-primary-soft text-primary [&>svg]:h-11 [&>svg]:w-11">
                <IconChat size={44} />
              </div>
              <h4 className="font-display text-base font-semibold text-heading">No conversation selected</h4>
              <p className="text-[13px] text-muted">Pick a conversation on the left, or start a fresh learning session.</p>
              <div className="mt-2 flex flex-wrap justify-center gap-2">
                <button
                  type="button"
                  onClick={handleNew}
                  className="rounded-full border border-line bg-surface px-3.5 py-[7px] text-xs font-medium text-ink hover:border-primary hover:bg-primary-soft hover:text-primary"
                >
                  Start a new conversation
                </button>
              </div>
            </div>
          </div>
        ) : (
          <ChatThread
            key={conversationId}
            messages={activeMessages}
            sending={sending}
            loading={loadingMsgs}
            onSend={handleSend}
            qaDisabled={sending || !!pendingAction}
            qaPendingId={pendingAction}
            qaConversationId={conversationId}
            onQuickAction={handleQuickAction}
            actionError={actionError}
            onDismissActionError={() => setActionError(null)}
          />
        )}
      </div>
      </div>

      {showThread && (
        <SourcesPanel
          messages={activeMessages}
          open={sourcesOpen}
          onClose={() => setSourcesOpen(false)}
        />
      )}

      <RenameModal
        open={!!renameTarget}
        initial={renameTarget?.title}
        saving={renameSaving}
        error={renameError}
        onSave={handleRenameSave}
        onClose={() => setRenameTarget(null)}
      />
      <ConfirmModal
        open={!!deleteTarget}
        title="Delete conversation?"
        message={`“${deleteTarget?.title || 'This conversation'}” and its message history will be permanently removed. This cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
