import { motion } from 'framer-motion';
import { IconChat, IconPlus, IconPencil, IconTrash, IconX, IconChevron } from '../../../../components/icons/Icons.jsx';

function groupLabel(dateStr) {
  const d = dateStr ? new Date(dateStr) : null;
  if (!d || Number.isNaN(d.getTime())) return 'Older';
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  if (d >= startOfToday) return 'Today';
  if (d >= startOfYesterday) return 'Yesterday';
  return 'Older';
}

function groupConversations(conversations) {
  const groups = { Today: [], Yesterday: [], Older: [] };
  for (const c of conversations || []) {
    groups[groupLabel(c.updated_at || c.created_at)].push(c);
  }
  return ['Today', 'Yesterday', 'Older'].filter((g) => groups[g].length > 0).map((g) => ({ label: g, items: groups[g] }));
}

const iconBtn =
  'inline-flex items-center justify-center rounded-md p-[5px] text-muted transition-colors hover:bg-surface hover:text-ink [&>svg]:h-3.5 [&>svg]:w-3.5';

export default function ConversationSidebar({
  conversations,
  conversationsMeta,
  onPage,
  activeId,
  creating,
  createError,
  listLoading,
  listError,
  navOpen,
  onCloseNav,
  onSelect,
  onNew,
  onRetryList,
  onRename,
  onDelete,
  collapsed,
  onCollapse,
  onExpand,
}) {
  const groups = groupConversations(conversations);

  // Collapsed desktop rail: the chat absorbs the freed width via flex.
  // (On mobile the rail stays hidden; the drawer + header button apply.)
  if (collapsed) {
    return (
      <div
        aria-label="Conversations (collapsed)"
        className="hidden w-12 shrink-0 self-stretch flex-col items-center gap-2 rounded-card border border-line bg-surface py-3 shadow-sm lg:flex lg:rounded-none lg:border-0 lg:border-r lg:border-line lg:shadow-none"
      >
        <button
          type="button"
          onClick={onExpand}
          aria-label="Expand conversations panel"
          title="Expand conversations"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]"
        >
          <IconChevron />
        </button>
        <button
          type="button"
          onClick={onNew}
          disabled={creating}
          aria-label="Start a new conversation"
          title="New conversation"
          className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary text-white hover:bg-primary-dark disabled:opacity-60 [&>svg]:h-4 [&>svg]:w-4"
        >
          <IconPlus size={16} />
        </button>
        {(conversations || []).length > 0 && (
          <span className="mt-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-canvas px-1 text-[10px] font-bold text-muted" title={`${conversations.length} conversation(s)`}>
            {conversations.length}
          </span>
        )}
      </div>
    );
  }

  return (
    <>
      {navOpen && (
        <div className="fixed inset-0 z-[60] bg-black/30 lg:hidden" onClick={onCloseNav} aria-hidden="true" />
      )}
      <nav
        aria-label="Tutor conversations"
        className={`fixed bottom-0 left-0 top-0 z-[61] flex w-[300px] max-w-[84vw] -translate-x-full flex-col gap-2.5 border-r border-line bg-surface p-3 transition-transform duration-200 lg:static lg:z-auto lg:h-auto lg:min-h-0 lg:w-48 lg:translate-x-0 lg:shrink-0 lg:self-stretch lg:rounded-none lg:border-0 lg:border-r lg:border-line lg:shadow-none lg:transition-none ${
          navOpen ? 'translate-x-0' : ''
        }`}
      >
        <div className="flex items-center gap-1 px-1 pt-1">
          <button
            type="button"
            className={`${iconBtn} hidden lg:inline-flex`}
            onClick={onCollapse}
            aria-label="Collapse conversations panel"
            title="Collapse conversations"
          >
            <span className="inline-flex rotate-180 [&>svg]:h-3.5 [&>svg]:w-3.5"><IconChevron /></span>
          </button>
          <span className="min-w-0 flex-1" aria-hidden="true" />
          <button
            type="button"
            onClick={onNew}
            disabled={creating}
            aria-label="Start a new conversation"
            title="New conversation"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-primary text-white hover:bg-primary-dark disabled:animate-pulse disabled:opacity-60 [&>svg]:h-4 [&>svg]:w-4"
          >
            <IconPlus size={16} />
          </button>
          <button
            type="button"
            className={`${iconBtn} lg:hidden`}
            onClick={onCloseNav}
            aria-label="Close conversations"
          >
            <IconX size={16} />
          </button>
        </div>
        {createError && (
          <p className="px-1 text-xs leading-relaxed text-danger" role="alert">
            {createError}{' '}
            <button type="button" className="rounded px-2 py-0.5 text-xs font-medium text-muted hover:bg-primary-soft hover:text-primary" onClick={onNew}>Retry</button>
          </p>
        )}
        <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto" role="list">
          {listLoading && (conversations || []).length === 0 && (
            <div className="px-1 py-2 text-xs text-muted">Loading conversations…</div>
          )}
          {!listLoading && !listError && (conversations || []).length === 0 && (
            <div className="px-1 py-2 text-xs text-muted">No conversations yet. Start your first one above.</div>
          )}
          {listError && (conversations || []).length === 0 && (
            <div className="px-1 py-2">
              <p className="text-xs leading-relaxed text-danger" role="alert">
                {listError}{' '}
                <button type="button" className="rounded px-2 py-0.5 text-xs font-medium text-muted hover:bg-primary-soft hover:text-primary" onClick={onRetryList}>Retry</button>
              </p>
            </div>
          )}
          {groups.map((g) => (
            <div key={g.label} className="flex flex-col gap-0.5">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
                {g.label}
              </div>
              {g.items.map((c) => {
                const isActive = c.id === activeId;
                return (
                  <motion.div key={c.id} role="listitem" layout transition={{ duration: 0.18 }}>
                    <div className={`group flex items-center gap-0.5 rounded-md ${isActive ? 'bg-primary-soft' : 'hover:bg-canvas'}`}>
                      <button
                        type="button"
                        onClick={() => onSelect(c.id)}
                        aria-current={isActive ? 'true' : undefined}
                        aria-label={`Open conversation ${c.title}`}
                        title={c.title}
                        className="flex min-w-0 flex-1 items-center gap-2 rounded-md p-2 text-left"
                      >
                        <span className={`inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-md [&>svg]:h-4 [&>svg]:w-4 ${isActive ? 'bg-surface text-primary' : 'bg-canvas text-muted'}`}>
                          <IconChat size={16} />
                        </span>
                        <span className="flex min-w-0 flex-1 flex-col leading-snug">
                          <span className="truncate text-[13px] font-semibold text-ink">
                            {c.title || 'New conversation'}
                          </span>
                        </span>
                      </button>
                      <span className="hidden shrink-0 items-center gap-0.5 pr-1 group-hover:inline-flex group-focus-within:inline-flex">
                        <button
                          type="button"
                          className={iconBtn}
                          onClick={() => onRename(c)}
                          aria-label={`Rename conversation ${c.title}`}
                          title="Rename"
                        >
                          <IconPencil size={14} />
                        </button>
                        <button
                          type="button"
                          className={iconBtn}
                          onClick={() => onDelete(c)}
                          aria-label={`Delete conversation ${c.title}`}
                          title="Delete"
                        >
                          <IconTrash size={14} />
                        </button>
                      </span>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          ))}
          {(conversationsMeta?.pages || 0) > 1 && (
            <div className="flex items-center justify-between gap-1 px-2 py-1 text-[11px] text-muted">
              <span>Page {conversationsMeta.page} of {conversationsMeta.pages}</span>
              <span className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={(conversationsMeta.page || 1) <= 1}
                  onClick={() => onPage && onPage(conversationsMeta.page - 1)}
                  className={iconBtn}
                  aria-label="Previous conversations page"
                >←</button>
                <button
                  type="button"
                  disabled={(conversationsMeta.page || 1) >= conversationsMeta.pages}
                  onClick={() => onPage && onPage(conversationsMeta.page + 1)}
                  className={iconBtn}
                  aria-label="Next conversations page"
                >→</button>
              </span>
            </div>
          )}
        </div>
      </nav>
    </>
  );
}
