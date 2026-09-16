import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { loadSpaces, loadProjects } from '../../features/project/spaceProjectSlice.js';
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

  return (
    <div className="dashboard">
      <div className="dash-head">
        <h2>Learning Dashboard</h2>
        {first && (
          <button className="primary" onClick={() => navigate(`/spaces/${first.spaceId}/projects/${first.id}`)}>
            Continue Learning
          </button>
        )}
      </div>
      <div className="card-grid">
        {allProjects.map((p, i) => (
          <motion.div
            key={p.id}
            className="dash-card"
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            onClick={() => navigate(`/spaces/${p.spaceId}/projects/${p.id}`)}
          >
            <h4>{p.name}</h4>
            <p>{p.description || 'No description'}</p>
            <div className="progress"><div style={{ width: `${p.overall_progress || 0}%` }} /></div>
            <small>{p.overall_progress || 0}% complete</small>
          </motion.div>
        ))}
      </div>
      {allProjects.length === 0 && <p className="muted">No projects yet. Create a Space and Project to begin.</p>}
    </div>
  );
}
