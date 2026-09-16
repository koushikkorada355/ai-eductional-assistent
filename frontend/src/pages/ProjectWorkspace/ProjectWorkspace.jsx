import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import Materials from './Tabs/Materials/Materials.jsx';
import AITutor from './Tabs/AITutor/AITutor.jsx';
import Quiz from './Tabs/Quiz/Quiz.jsx';
import Analytics from './Tabs/Analytics/Analytics.jsx';
import './ProjectWorkspace.css';

const TABS = ['Materials', 'AI Tutor', 'Quiz', 'Analytics'];

export default function ProjectWorkspace() {
  const { spaceId, projectId } = useParams();
  const [tab, setTab] = useState('Materials');
  return (
    <div className="workspace">
      <div className="tabs">
        {TABS.map((t) => (
          <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>
      <motion.div key={tab} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        {tab === 'Materials' && <Materials spaceId={spaceId} projectId={projectId} />}
        {tab === 'AI Tutor' && <AITutor spaceId={spaceId} projectId={projectId} />}
        {tab === 'Quiz' && <Quiz spaceId={spaceId} projectId={projectId} />}
        {tab === 'Analytics' && <Analytics />}
      </motion.div>
    </div>
  );
}
