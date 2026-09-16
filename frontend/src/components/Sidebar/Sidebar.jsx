import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams } from 'react-router-dom';
import {
  loadSpaces, loadProjects, addSpace, editSpace, removeSpace,
  addProject, editProject, removeProject,
} from '../../features/project/spaceProjectSlice.js';
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

  const confirmDeleteSpace = (sp) => {
    if (window.confirm(`Delete space "${sp.name}" and all its projects?`)) {
      dispatch(removeSpace({ spaceId: sp.id }));
    }
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

  const confirmDeleteProject = (spaceId, p) => {
    if (window.confirm(`Delete project "${p.name}"?`)) {
      dispatch(removeProject({ spaceId, projectId: p.id }));
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <h4>Spaces</h4>
        <button className="mini-btn" onClick={() => setShowSpaceForm((v) => !v)}>+ New</button>
      </div>
      {showSpaceForm && (
        <form className="inline-form" onSubmit={submitSpace}>
          <input value={spaceName} onChange={(e) => setSpaceName(e.target.value)} placeholder="Space name" />
          <button type="submit">Add</button>
        </form>
      )}
      {spaces.length === 0 && <p className="muted">No spaces yet.</p>}
      {spaces.map((sp) => (
        <div key={sp.id} className="space-block">
          {editingSpace === sp.id ? (
            <form className="inline-form" onSubmit={(e) => submitEditSpace(e, sp.id)}>
              <input value={editSpaceName} onChange={(e) => setEditSpaceName(e.target.value)} />
              <button type="submit">Save</button>
              <button type="button" className="ghost" onClick={() => setEditingSpace(null)}>✕</button>
            </form>
          ) : (
            <div className="space-row">
              <button className="space-name" onClick={() => { toggle(sp.id); dispatch(loadProjects(sp.id)); }}>
                <span className={`caret ${isOpen(sp.id) ? 'open' : ''}`}>▸</span>
                {sp.name}
              </button>
              <span className="row-actions">
                <button title="Rename space" onClick={() => { setEditingSpace(sp.id); setEditSpaceName(sp.name); }}>✎</button>
                <button title="Delete space" onClick={() => confirmDeleteSpace(sp)}>🗑</button>
              </span>
            </div>
          )}
          {isOpen(sp.id) && (
            <div className="project-list">
              {(projectsBySpace[sp.id] || []).map((p) => (
                editingProject === p.id ? (
                  <form key={p.id} className="inline-form" onSubmit={(e) => submitEditProject(e, sp.id, p.id)}>
                    <input value={editProjectName} onChange={(e) => setEditProjectName(e.target.value)} />
                    <button type="submit">Save</button>
                    <button type="button" className="ghost" onClick={() => setEditingProject(null)}>✕</button>
                  </form>
                ) : (
                  <div key={p.id} className="project-row">
                    <button
                      className={`project-link ${p.id === activeProject ? 'active' : ''}`}
                      onClick={() => navigate(`/spaces/${sp.id}/projects/${p.id}`)}
                    >
                      {p.name}
                    </button>
                    <span className="row-actions">
                      <button title="Rename project" onClick={() => { setEditingProject(p.id); setEditProjectName(p.name); }}>✎</button>
                      <button title="Delete project" onClick={() => confirmDeleteProject(sp.id, p)}>🗑</button>
                    </span>
                  </div>
                )
              ))}
              {(projectsBySpace[sp.id] || []).length === 0 && (
                <span className="muted small">No projects</span>
              )}
              {projectFormFor === sp.id ? (
                <form className="inline-form stacked" onSubmit={(e) => submitProject(e, sp.id)}>
                  <input value={projectName} onChange={(e) => setProjectName(e.target.value)} placeholder="Project name" />
                  <input value={projectGoal} onChange={(e) => setProjectGoal(e.target.value)} placeholder="Learning goal" />
                  <div>
                    <button type="submit">Add</button>
                    <button type="button" className="ghost" onClick={() => setProjectFormFor(null)}>✕</button>
                  </div>
                </form>
              ) : (
                <button className="mini-btn" onClick={() => setProjectFormFor(sp.id)}>+ Project</button>
              )}
            </div>
          )}
        </div>
      ))}
    </aside>
  );
}
