import { motion } from 'framer-motion';
import './MasteryBars.css';

export default function MasteryBars({ concepts }) {
  if (!concepts || concepts.length === 0) {
    return <p className="muted">No concepts yet. Upload PDFs to generate mastery tracking.</p>;
  }
  return (
    <div className="mastery-list">
      {concepts.map((c, i) => (
        <motion.div
          key={c.id}
          className="mastery-row"
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05 }}
        >
          <div className="mastery-label">
            <span>{c.name}</span>
            <span>{Math.round(c.mastery_level)}%</span>
          </div>
          <div className="mastery-track">
            <motion.div
              className="mastery-fill"
              animate={{ width: `${Math.min(100, Math.max(0, c.mastery_level))}%` }}
              transition={{ duration: 0.6 }}
            />
          </div>
        </motion.div>
      ))}
    </div>
  );
}
