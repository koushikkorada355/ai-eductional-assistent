import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Materials from './Tabs/Materials/Materials.jsx';
import AITutor from './Tabs/AITutor/AITutor.jsx';
import Quiz from './Tabs/Quiz/Quiz.jsx';
import Analytics from './Tabs/Analytics/Analytics.jsx';
import Assignments from './Tabs/Assignments/Assignments.jsx';
import Concepts from './Tabs/Concepts/Concepts.jsx';
import { tabFromLocation, tabHref } from './tabs.js';
import './ProjectWorkspace.css';

export default function ProjectWorkspace() {
  const { spaceId, projectId, conversationId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  // The left sidebar owns section navigation; the tab always mirrors the URL
  // so deep links, refresh, and back/forward land on the right section.
  const urlTab = tabFromLocation(location.pathname, searchParams);
  const [tab, setTab] = useState(urlTab);

  useEffect(() => {
    setTab(urlTab);
  }, [urlTab]);

  const handleSelectConversation = (id) => {
    navigate(id ? `${tabHref('AI Tutor', spaceId, projectId)}/${id}` : tabHref('AI Tutor', spaceId, projectId));
  };

  const isTutor = tab === 'AI Tutor';

  return (
    <div className="workspace">
      {/* No second header here: the app header breadcrumb already carries
          Space / Project / Section context, and every tab owns its own
          page header. One bar only. */}
      <div className={isTutor ? 'ws-body ws-body-tutor' : 'ws-body'}>
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            className={isTutor ? 'ws-tutor-fill' : undefined}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {tab === 'Materials' && <Materials spaceId={spaceId} projectId={projectId} />}
            {tab === 'Concepts' && <Concepts spaceId={spaceId} projectId={projectId} />}
            {tab === 'AI Tutor' && (
              <AITutor
                spaceId={spaceId}
                projectId={projectId}
                conversationId={conversationId || null}
                onSelectConversation={handleSelectConversation}
                onOpenQuiz={() => navigate(tabHref('Quiz', spaceId, projectId))}
              />
            )}
            {tab === 'Quiz' && <Quiz spaceId={spaceId} projectId={projectId} />}
            {tab === 'Assignments' && <Assignments spaceId={spaceId} projectId={projectId} />}
            {tab === 'Analytics' && <Analytics spaceId={spaceId} projectId={projectId} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
