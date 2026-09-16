import { motion, AnimatePresence } from 'framer-motion';
import './ConfirmModal.css';

export default function ConfirmModal({ open, title, message, confirmLabel = 'Delete', onConfirm, onCancel }) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onCancel}
        >
          <motion.div
            className="modal-card"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>{title}</h3>
            <p className="muted">{message}</p>
            <div className="modal-actions">
              <button className="secondary" onClick={onCancel}>Cancel</button>
              <button className="danger-btn" onClick={onConfirm}>{confirmLabel}</button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
