import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  loadSpaces, loadProjects, addSpace, editSpace, removeSpace,
  addProject, editProject, removeProject,
} from '../../features/project/spaceProjectSlice.js';
import ConfirmModal from '../ConfirmModal/ConfirmModal.jsx';
import { IconChevron, IconPencil, IconTrash, IconX, IconFile, IconPlus } from '../icons/Icons.jsx';
import './Sidebar.css';

export default function Sidebar() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { projectId: activeProject } = useParams();
  const { spaces, projectsBySpace } = useSelector((s) => s.spaceProject);
  const [expanded, setExpanded] = useState({});
  const [showSpaceForm, setShowSpaceForm] = useState(false);
  const [spaceName, setSpaceName] = useState('');
  const [editingSpace, setEditingSpace] = useState(null);
  const [editSpaceName, setEditSpaceName] = useState('');
  const [projectFormFor, setProjectFormFor] = useState(null);
  const [projectName, setProjectName] = useState('');
  const [projectGoal, setProjectGoal] = useState('');
  const [editingProject, setEditingProject] = useState(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [confirm, setConfirm] = useState(null);

  useEffect(() => { dispatch(loadSpaces()); }, [dispatch]);
  useEffect(() => {
    spaces.forEach((sp) => dispatch(loadProjects(sp.id)));
  }, [dispatch, spaces.length]);

  const isOpen = (id) => expanded[id] !== false;
  const toggle = (id) => setExpanded((e) => ({ ...e, [id]: !isOpen(id) }));

  const submitSpace = (e) => {
    e.preventDefault();
    if (!spaceName.trim()) return;
    dispatch(addSpace({ name: spaceName.trim() }));
    setSpaceName('');
    setShowSpaceForm(false);
  };

  const submitEditSpace = (e, id) => {
    e.preventDefault();
    if (!editSpaceName.trim()) return;
    dispatch(editSpace({ spaceId: id, payload: { name: editSpaceName.trim() } }));
    setEditingSpace(null);
  };

  const submitProject = (e, spaceId) => {
    e.preventDefault();
    if (!projectName.trim() || !projectGoal.trim()) return;
    dispatch(addProject({
      spaceId,
      payload: { name: projectName.trim(), description: projectName.trim(), learning_goal: projectGoal.trim() },
    }));
    setProjectName('');
    setProjectGoal('');
    setProjectFormFor(null);
  };

  const submitEditProject = (e, spaceId, projectId) => {
    e.preventDefault();
    if (!editProjectName.trim()) return;
    dispatch(editProject({ spaceId, projectId, payload: { name: editProjectName.trim() } }));
    setEditingProject(null);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h4>My Learning Spaces</h4>
        <button className="mini-btn" onClick={() => setShowSpaceForm((v) => !v)}><IconPlus /> New</button>
      </div>
      <AnimatePresence>
        {showSpaceForm && (
          <motion.form
            className="inline-form"
            onSubmit={submitSpace}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            <input value={spaceName} onChange={(e) => setSpaceName(e.target.value)} placeholder="Space name" />
            <button type="submit">Add</button>
          </motion.form>
        )}
      </AnimatePresence>
      {spaces.length === 0 && <p className="muted">No spaces yet. Create your first learning space.</p>}
      {spaces.map((sp, si) => (
        <motion.div
          key={sp.id}
          className="space-block"
          initial={{ opacity: 0, x: -12 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: si * 0.05 }}
        >
          {editingSpace === sp.id ? (
            <form className="inline-form" onSubmit={(e) => submitEditSpace(e, sp.id)}>
              <input value={editSpaceName} onChange={(e) => setEditSpaceName(e.target.value)} />
              <button type="submit">Save</button>
              <button type="button" className="ghost" onClick={() => setEditingSpace(null)}><IconX /></button>
            </form>
          ) : (
            <div className="space-row">
              <button className="space-name" onClick={() => { toggle(sp.id); dispatch(loadProjects(sp.id)); }}>
                <span className={`caret ${isOpen(sp.id) ? 'open' : ''}`}><IconChevron /></span>
                {sp.name}
              </button>
              <span className="row-actions">
                <button title="Rename space" onClick={() => { setEditingSpace(sp.id); setEditSpaceName(sp.name); }}><IconPencil /></button>
                <button
                  title="Delete space"
                  onClick={() => setConfirm({
                    title: 'Delete space?',
                    message: `"${sp.name}" and all its projects will be permanently removed.`,
                    onConfirm: () => { dispatch(removeSpace({ spaceId: sp.id })); setConfirm(null); },
                  })}
                ><IconTrash /></button>
              </span>
            </div>
          )}
          <AnimatePresence initial={false}>
            {isOpen(sp.id) && (
              <motion.div
                className="project-list"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.18 }}
              >
                {(projectsBySpace[sp.id] || []).map((p) => (
                  editingProject === p.id ? (
                    <form key={p.id} className="inline-form" onSubmit={(e) => submitEditProject(e, sp.id, p.id)}>
                      <input value={editProjectName} onChange={(e) => setEditProjectName(e.target.value)} />
                      <button type="submit">Save</button>
                      <button type="button" className="ghost" onClick={() => setEditingProject(null)}><IconX /></button>
                    </form>
                  ) : (
                    <div key={p.id} className="project-row">
                      <button
                        className={`project-link ${p.id === activeProject ? 'active' : ''}`}
                        onClick={() => navigate(`/spaces/${sp.id}/projects/${p.id}`)}
                      >
                        <IconFile size={18} />
                        {p.name}
                      </button>
                      <span className="row-actions">
                        <button title="Rename project" onClick={() => { setEditingProject(p.id); setEditProjectName(p.name); }}><IconPencil /></button>
                        <button
                          title="Delete project"
                          onClick={() => setConfirm({
                            title: 'Delete project?',
                            message: `"${p.name}" and its materials will be permanently removed.`,
                            onConfirm: () => { dispatch(removeProject({ spaceId: sp.id, projectId: p.id })); setConfirm(null); },
                          })}
                        ><IconTrash /></button>
                      </span>
                    </div>
                  )
                ))}
                {(projectsBySpace[sp.id] || []).length === 0 && (
                  <span className="muted small">No projects yet</span>
                )}
                {projectFormFor === sp.id ? (
                  <form className="inline-form stacked" onSubmit={(e) => submitProject(e, sp.id)}>
                    <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="Project name" />
                    <input value={projectGoal} onChange={(e) => setProjectGoal(e.target.value)} placeholder="Learning goal" />
                    <div className="form-row">
                      <button type="submit">Add</button>
                      <button type="button" className="ghost" onClick={() => setProjectFormFor(null)}><IconX /></button>
                    </div>
                  </form>
                ) : (
                  <button className="mini-btn" onClick={() => setProjectFormFor(sp.id)}><IconPlus /> Project</button>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      ))}
      <ConfirmModal
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
      />
    </aside>
  );
}
