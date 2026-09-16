import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Materials from './Tabs/Materials/Materials.jsx';
import AITutor from './Tabs/AITutor/AITutor.jsx';
import Quiz from './Tabs/Quiz/Quiz.jsx';
import Analytics from './Tabs/Analytics/Analytics.jsx';
import Assignments from './Tabs/Assignments/Assignments.jsx';
import Concepts from './Tabs/Concepts/Concepts.jsx';
import { IconFolder, IconChat, IconTarget, IconChart, IconFile, IconBook } from '../../components/icons/Icons.jsx';
import './ProjectWorkspace.css';

const TABS = [
  { id: 'Materials', Icon: IconFolder },
  { id: 'Concepts', Icon: IconBook },
  { id: 'AI Tutor', Icon: IconChat },
  { id: 'Quiz', Icon: IconTarget },
  { id: 'Assignments', Icon: IconFile },
  { id: 'Analytics', Icon: IconChart },
];

export default function ProjectWorkspace() {
  const { spaceId, projectId } = useParams();
  const [tab, setTab] = useState('Materials');
  return (
    <div className="workspace">
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={tab === t.id ? 'active' : ''}
            onClick={() => setTab(t.id)}
          >
            {tab === t.id && (
              <motion.span
                className="tab-pill"
                layoutId="tab-pill"
                transition={{ type: 'spring', stiffness: 420, damping: 34 }}
              />
            )}
            <span className="tab-icon"><t.Icon size={19} /></span>
            <span className="tab-label">{t.id}</span>
          </button>
        ))}
      </div>
      <AnimatePresence mode="wait">
        <motion.div
          key={tab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
        >
        {tab === 'Materials' && <Materials spaceId={spaceId} projectId={projectId} />}
        {tab === 'Concepts' && <Concepts spaceId={spaceId} projectId={projectId} />}
        {tab === 'AI Tutor' && <AITutor spaceId={spaceId} projectId={projectId} />}
        {tab === 'Quiz' && <Quiz spaceId={spaceId} projectId={projectId} />}
        {tab === 'Assignments' && <Assignments spaceId={spaceId} projectId={projectId} />}
        {tab === 'Analytics' && <Analytics />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
