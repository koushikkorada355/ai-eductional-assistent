import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { loadSpaces, loadProjects } from '../../features/project/spaceProjectSlice.js';
import { IconArrowRight } from '../../components/icons/Icons.jsx';
import './Dashboard.css';

export default function Dashboard() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { spaces, projectsBySpace } = useSelector((s) => s.spaceProject);

  useEffect(() => { dispatch(loadSpaces()); }, [dispatch]);

  const allProjects = Object.entries(projectsBySpace).flatMap(([sid, list]) =>
    (list || []).map((p) => ({ ...p, spaceId: sid }))
  );

  useEffect(() => {
    spaces.forEach((sp) => dispatch(loadProjects(sp.id)));
  }, [dispatch, spaces.length]);

  const first = allProjects[0];
  const spaceName = (sid) => spaces.find((s) => s.id === sid)?.name || 'Space';

  return (
    <div className="dashboard">
      <motion.div
        className="dash-hero"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div>
          <h2>Learning Dashboard</h2>
          <p className="muted">
            {allProjects.length === 0
              ? 'Create a space and project from the sidebar to begin.'
              : `You're working across ${spaces.length} space${spaces.length === 1 ? '' : 's'} and ${allProjects.length} project${allProjects.length === 1 ? '' : 's'}.`}
          </p>
        </div>
        {first && (
          <motion.button
            className="primary"
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate(`/spaces/${first.spaceId}/projects/${first.id}`)}
          >
            Continue Learning <IconArrowRight size={18} />
          </motion.button>
        )}
      </motion.div>
      <div className="card-grid">
        {allProjects.map((p, i) => (
          <motion.div
            key={p.id}
            className="dash-card"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.35 }}
            whileHover={{ y: -5, boxShadow: '0 18px 44px -12px rgba(15,30,61,0.22)' }}
            whileTap={{ scale: 0.99 }}
            onClick={() => navigate(`/spaces/${p.spaceId}/projects/${p.id}`)}
          >
            <span className="dash-space">{spaceName(p.spaceId)}</span>
            <h4>{p.name}</h4>
            <p className="muted">{p.description || 'No description'}</p>
            <div className="progress"><motion.div
              initial={{ width: 0 }}
              animate={{ width: `${p.overall_progress || 0}%` }}
              transition={{ delay: 0.2 + Math.min(i * 0.02, 0.4), duration: 0.6 }}
            /></div>
            <small>{p.overall_progress || 0}% complete</small>
          </motion.div>
        ))}
      </div>
      {allProjects.length === 0 && (
        <div className="placeholder-card">
          <h3>No projects yet</h3>
          <p className="muted">Use the <strong>+ New</strong> button in the sidebar to create a Space, then add a Project inside it.</p>
        </div>
      )}
    </div>
  );
}
