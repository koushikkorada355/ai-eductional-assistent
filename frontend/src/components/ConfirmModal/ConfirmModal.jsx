import { motion, AnimatePresence } from 'framer-motion';

export default function ConfirmModal({ open, title, message, confirmLabel = 'Delete', onConfirm, onCancel }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/30 p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
            className="flex w-[320px] max-w-full flex-col gap-2 rounded-card bg-surface p-6 shadow-lg"
          >
            <h3 className="font-display text-[15px] font-semibold text-heading">{title}</h3>
            <p className="text-[13px] text-muted">{message}</p>
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={onCancel}
                className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirm}
                className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-danger px-4 text-sm font-medium text-white hover:bg-[#991b1b]"
              >
                {confirmLabel}
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
