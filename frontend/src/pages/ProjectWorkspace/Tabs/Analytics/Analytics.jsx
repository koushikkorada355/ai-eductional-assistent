import { motion } from 'framer-motion';
import { IconChart } from '../../../../components/icons/Icons.jsx';
import './Analytics.css';

export default function Analytics() {
  return (
    <motion.div
      className="placeholder-card analytics-empty"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
    >
      <div className="analytics-icon"><IconChart size={48} /></div>
      <h3>Learning Analytics</h3>
      <p className="muted">Concept mastery, progress trends, and recommendations will appear here once quiz activity is available. Complete a quiz to unlock your insights.</p>
    </motion.div>
  );
}
