import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { normalizeCitations } from '../../../../features/tutor/tutorSlice.js';
import { IconX } from '../../../../components/icons/Icons.jsx';

/* Supporting evidence panel. On xl+ it docks beside the chat; below that it
 * becomes a right-side overlay drawer so the conversation keeps full width. */
export default function SourcesPanel({ messages, open, onClose }) {
  const [citationModal, setCitationModal] = useState(null);

  // Sidebar follows the latest assistant reply of THIS conversation only.
  // General / small-talk replies carry no citations, so the panel correctly
  // goes empty instead of showing stale sources from an older answer.
  const reversed = [...(messages || [])].reverse();
  const latestAssistant = reversed.find((m) => m.role === 'assistant') || null;
  const sidebarCitations = normalizeCitations(latestAssistant?.citations);

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-[60] bg-black/30 xl:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        aria-label="Sources"
        aria-hidden={!open}
        className={`fixed bottom-0 right-0 top-0 z-[61] flex w-[320px] max-w-[84vw] flex-col gap-2 overflow-y-auto border-l border-line bg-surface p-3 transition-transform duration-200 xl:static xl:z-auto xl:w-72 xl:shrink-0 xl:self-stretch xl:rounded-card xl:border xl:shadow-sm ${
          open ? 'translate-x-0' : 'translate-x-full xl:hidden'
        }`}
      >
        <div className="flex items-center justify-between px-1 pt-1">
          <div className="text-[11px] font-bold uppercase tracking-[0.06em] text-muted">
            Sources {sidebarCitations.length > 0 && `· ${sidebarCitations.length}`}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sources"
            className="inline-flex items-center justify-center rounded-md p-[5px] text-muted hover:bg-canvas hover:text-ink xl:hidden [&>svg]:h-4 [&>svg]:w-4"
          >
            <IconX size={16} />
          </button>
        </div>
        {sidebarCitations.length === 0 && (
          <div className="px-1 py-1 text-xs text-muted">
            {latestAssistant
              ? 'No sources for this reply — general answers need no citations.'
              : 'No sources yet — ask a question about your documents.'}
          </div>
        )}
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
          {sidebarCitations.map((c, j) => (
            <button
              key={j}
              type="button"
              onClick={() => setCitationModal(c)}
              className="flex w-full shrink-0 flex-col items-start gap-1 rounded-md bg-canvas p-3 text-left transition-colors hover:bg-primary-soft"
            >
              <span className="text-xs font-semibold text-ink">{c.pdf_name}</span>
              <span className="text-[11px] font-semibold text-primary">Page {c.page_number}</span>
              <p className="text-xs text-muted">{c.chunk_excerpt}</p>
            </button>
          ))}
        </div>
      </aside>
      <AnimatePresence>
        {citationModal && (
          <motion.div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 p-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCitationModal(null)}
          >
            <motion.div
              className="flex w-full max-w-lg flex-col gap-2 rounded-card bg-surface p-6 shadow-lg"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96 }}
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label="Citation detail"
            >
              <span className="text-xs font-semibold text-ink">{citationModal.pdf_name}</span>
              <span className="text-[11px] font-semibold text-primary">Page {citationModal.page_number}</span>
              <p className="rounded-md border border-primary/20 bg-primary-soft px-3.5 py-3 text-[13px] leading-relaxed text-ink">
                {citationModal.chunk_excerpt}
              </p>
              <div className="mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setCitationModal(null)}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                >
                  Close
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
