import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  loadSpaces, loadProjects, addSpace, editSpace, removeSpace,
  addProject, editProject, removeProject,
} from '../../features/project/spaceProjectSlice.js';
import ConfirmModal from '../../components/ConfirmModal/ConfirmModal.jsx';
import { PageHeader, EmptyState } from '../../components/ui/ui.jsx';
import {
  IconFolder, IconPlus, IconPencil, IconTrash, IconX, IconArrowRight, IconArrowLeft,
} from '../../components/icons/Icons.jsx';

const iconBtn =
  'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-canvas hover:text-primary [&>svg]:h-4 [&>svg]:w-4';

const inputCls =
  'min-h-9 min-w-0 rounded-md border border-line bg-surface px-3 text-sm text-ink focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary';

/* Spaces workspace — two progressive modes, never the full tree at once:
 * - No ?space=: every space as a card (name, count, Open Space →). No
 *   project rows here; projects belong to the focused-space view.
 * - ?space=ID: that space only — its projects, New Project, rename/delete.
 * Sidebar actions route here (?create=space|project) to open the matching
 * form; params are cleaned after submit/cancel. */
export default function Spaces() {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { spaces, projectsBySpace } = useSelector((s) => s.spaceProject);

  const [showSpaceForm, setShowSpaceForm] = useState(false);
  const [spaceName, setSpaceName] = useState('');
  const [editingSpace, setEditingSpace] = useState(null);
  const [editSpaceName, setEditSpaceName] = useState('');
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectGoal, setProjectGoal] = useState('');
  const [editingProject, setEditingProject] = useState(null);
  const [editProjectName, setEditProjectName] = useState('');
  const [confirm, setConfirm] = useState(null);

  useEffect(() => { dispatch(loadSpaces()); }, [dispatch]);
  useEffect(() => {
    spaces.forEach((sp) => dispatch(loadProjects(sp.id)));
  }, [dispatch, spaces.length]);

  const focusId = searchParams.get('space');
  const createKind = searchParams.get('create');
  const focused = focusId ? spaces.find((s) => s.id === focusId) || null : null;
  const focusedProjects = focused ? projectsBySpace[focused.id] || [] : [];

  useEffect(() => {
    if (createKind === 'space') {
      setShowSpaceForm(true);
      setShowProjectForm(false);
    } else if (createKind === 'project' && focused) {
      setShowProjectForm(true);
      setShowSpaceForm(false);
    }
  }, [createKind, focused?.id]);

  const clearCreateParams = (keepSpace) => {
    navigate(keepSpace ? `/spaces?space=${keepSpace}` : '/spaces', { replace: true });
  };

  const cancelSpaceForm = () => {
    setShowSpaceForm(false);
    if (createKind === 'space') clearCreateParams(focused?.id || null);
  };

  const cancelProjectForm = () => {
    setShowProjectForm(false);
    if (createKind === 'project') clearCreateParams(focused?.id || null);
  };

  const submitSpace = (e) => {
    e.preventDefault();
    if (!spaceName.trim()) return;
    dispatch(addSpace({ name: spaceName.trim() }));
    setSpaceName('');
    setShowSpaceForm(false);
    if (createKind) clearCreateParams(null);
  };

  const submitEditSpace = (e, id) => {
    e.preventDefault();
    if (!editSpaceName.trim()) return;
    dispatch(editSpace({ spaceId: id, payload: { name: editSpaceName.trim() } }));
    setEditingSpace(null);
  };

  const submitProject = (e) => {
    e.preventDefault();
    if (!focused || !projectName.trim() || !projectGoal.trim()) return;
    dispatch(addProject({
      spaceId: focused.id,
      payload: { name: projectName.trim(), description: projectName.trim(), learning_goal: projectGoal.trim() },
    }));
    setProjectName('');
    setProjectGoal('');
    setShowProjectForm(false);
    if (createKind) clearCreateParams(focused.id);
  };

  const submitEditProject = (e, projectId) => {
    e.preventDefault();
    if (!focused || !editProjectName.trim()) return;
    dispatch(editProject({ spaceId: focused.id, projectId, payload: { name: editProjectName.trim() } }));
    setEditingProject(null);
  };

  const askDeleteSpace = (sp) => setConfirm({
    title: 'Delete space?',
    message: `"${sp.name}" and all its projects will be permanently removed.`,
    onConfirm: () => {
      dispatch(removeSpace({ spaceId: sp.id }));
      setConfirm(null);
      navigate('/spaces', { replace: true });
    },
  });

  const askDeleteProject = (p) => setConfirm({
    title: 'Delete project?',
    message: `"${p.name}" and its materials will be permanently removed.`,
    onConfirm: () => {
      dispatch(removeProject({ spaceId: focused.id, projectId: p.id }));
      setConfirm(null);
    },
  });

  const totalProjects = spaces.reduce((n, sp) => n + (projectsBySpace[sp.id] || []).length, 0);

  return (
    <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-6 px-6 py-8 max-sm:px-4 max-sm:py-5">
      {focused ? (
        <>
          <button
            type="button"
            onClick={() => navigate('/spaces')}
            className="inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]"
          >
            <IconArrowLeft size={18} /> All spaces
          </button>
          <PageHeader
            eyebrow={focused ? 'Space' : 'Workspace'}
            title={focused.name}
            sub={`${focusedProjects.length} project${focusedProjects.length === 1 ? '' : 's'} in this space. Select a project to open its workspace.`}
            actions={(
              <button
                type="button"
                onClick={() => setShowProjectForm((v) => !v)}
                className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark [&>svg]:h-4 [&>svg]:w-4"
              >
                <IconPlus size={16} /> New Project
              </button>
            )}
          />

          <AnimatePresence>
            {showProjectForm && (
              <motion.form
                onSubmit={submitProject}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="flex max-w-2xl flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm">
                  <h3 className="font-display text-sm font-semibold text-heading">Create new project in {focused.name}</h3>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink">
                      Project name
                      <input
                        value={projectName}
                        onChange={(e) => setProjectName(e.target.value)}
                        placeholder="e.g. Photosynthesis"
                        aria-label="Project name"
                        autoFocus
                        className={inputCls}
                      />
                    </label>
                    <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink">
                      Learning goal
                      <input
                        value={projectGoal}
                        onChange={(e) => setProjectGoal(e.target.value)}
                        placeholder="e.g. Master plant energy cycles"
                        aria-label="Learning goal"
                        className={inputCls}
                      />
                    </label>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={cancelProjectForm}
                      className="inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!projectName.trim() || !projectGoal.trim()}
                      className="inline-flex min-h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                    >
                      Create Project
                    </button>
                  </div>
                </div>
              </motion.form>
            )}
          </AnimatePresence>

          {focusedProjects.length === 0 ? (
            <EmptyState
              title="No projects in this space yet"
              body={`Create your first project in ${focused.name} to start learning.`}
              actions={(
                <button
                  type="button"
                  onClick={() => setShowProjectForm(true)}
                  className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark"
                >
                  <IconPlus size={16} /> New Project
                </button>
              )}
            />
          ) : (
            <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {focusedProjects.map((p) => (
                <li
                  key={p.id}
                  className="group flex flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm transition-all hover:border-primary hover:shadow-md"
                >
                  {editingProject === p.id ? (
                    <form className="flex min-w-0 flex-1 items-center gap-2" onSubmit={(e) => submitEditProject(e, p.id)}>
                      <input
                        value={editProjectName}
                        onChange={(e) => setEditProjectName(e.target.value)}
                        aria-label="Project name"
                        autoFocus
                        className={`${inputCls} flex-1`}
                      />
                      <button type="submit" className="inline-flex min-h-9 shrink-0 items-center rounded-md bg-primary px-3 text-sm font-medium text-white hover:bg-primary-dark">
                        Save
                      </button>
                      <button type="button" className={iconBtn} onClick={() => setEditingProject(null)} aria-label="Cancel">
                        <IconX size={16} />
                      </button>
                    </form>
                  ) : (
                    <>
                      <div className="flex items-center gap-3">
                        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary-soft font-display text-lg font-bold uppercase text-primary transition-transform group-hover:scale-105">
                          {(p.name || '?')[0]}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-ink">{p.name}</span>
                          <span className="block truncate text-xs text-muted">
                            {p.description || p.learning_goal || ''}
                            {p.created_at ? ` · ${new Date(p.created_at).toLocaleDateString()}` : ''}
                          </span>
                        </span>
                        <span className="flex shrink-0 items-center gap-0.5 opacity-100 transition-opacity focus-within:opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
                          <button type="button" className={iconBtn} title="Rename project" aria-label={`Rename project ${p.name}`} onClick={() => { setEditingProject(p.id); setEditProjectName(p.name); }}>
                            <IconPencil size={16} />
                          </button>
                          <button type="button" className={`${iconBtn} hover:!text-danger`} title="Delete project" aria-label={`Delete project ${p.name}`} onClick={() => askDeleteProject(p)}>
                            <IconTrash size={16} />
                          </button>
                        </span>
                      </div>
                      {p.overall_progress != null && (
                        <div className="flex items-center gap-2.5">
                          <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-canvas">
                            <div className="h-full rounded-full bg-primary" style={{ width: `${p.overall_progress}%` }} />
                          </div>
                          <span className="shrink-0 text-xs font-bold text-heading">{p.overall_progress}%</span>
                        </div>
                      )}
                      <div className="flex items-center justify-end border-t border-line pt-3">
                        <button
                          type="button"
                          onClick={() => navigate(`/spaces/${focused.id}/projects/${p.id}`)}
                          aria-label={`Open project ${p.name}`}
                          className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-semibold text-primary hover:bg-primary-soft [&>svg]:h-[18px] [&>svg]:w-[18px]"
                        >
                          Open Project <IconArrowRight size={18} />
                        </button>
                      </div>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      ) : (
        <>
          <PageHeader
            eyebrow="Workspace"
            title="Spaces"
            sub={spaces.length === 0
              ? 'Create a space first, then add projects inside it to start learning.'
              : `You have ${spaces.length} space${spaces.length === 1 ? '' : 's'} and ${totalProjects} project${totalProjects === 1 ? '' : 's'}. Open a space to see its projects.`}
            actions={(
              <button
                type="button"
                onClick={() => setShowSpaceForm((v) => !v)}
                className="inline-flex min-h-9 items-center gap-1.5 whitespace-nowrap rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark [&>svg]:h-4 [&>svg]:w-4"
              >
                <IconPlus size={16} /> New Space
              </button>
            )}
          />

          <AnimatePresence>
            {showSpaceForm && (
              <motion.form
                onSubmit={submitSpace}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="overflow-hidden"
              >
                <div className="flex max-w-2xl flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm">
                  <h3 className="font-display text-sm font-semibold text-heading">Create new space</h3>
                  <input
                    value={spaceName}
                    onChange={(e) => setSpaceName(e.target.value)}
                    placeholder="Space name, e.g. Machine Learning"
                    aria-label="Space name"
                    autoFocus
                    className={inputCls}
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={cancelSpaceForm}
                      className="inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!spaceName.trim()}
                      className="inline-flex min-h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
                    >
                      Create Space
                    </button>
                  </div>
                </div>
              </motion.form>
            )}
          </AnimatePresence>

          {spaces.length === 0 ? (
            <EmptyState
              title="No spaces yet"
              body="Spaces organize your learning. Create your first space above, then add a project inside it."
            />
          ) : (
            <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {spaces.map((sp) => {
                const count = (projectsBySpace[sp.id] || []).length;
                return (
                  <li
                    key={sp.id}
                    className="group flex flex-col gap-4 rounded-card border border-line bg-surface p-5 shadow-sm transition-all hover:border-primary hover:shadow-md"
                  >
                    {editingSpace === sp.id ? (
                      <form className="flex min-w-0 flex-1 items-center gap-2" onSubmit={(e) => submitEditSpace(e, sp.id)}>
                        <input
                          value={editSpaceName}
                          onChange={(e) => setEditSpaceName(e.target.value)}
                          aria-label="Space name"
                          autoFocus
                          className={`${inputCls} flex-1`}
                        />
                        <button type="submit" className="inline-flex min-h-9 shrink-0 items-center rounded-md bg-primary px-3 text-sm font-medium text-white hover:bg-primary-dark">
                          Save
                        </button>
                        <button type="button" className={iconBtn} onClick={() => setEditingSpace(null)} aria-label="Cancel">
                          <IconX size={16} />
                        </button>
                      </form>
                    ) : (
                      <>
                        <div className="flex items-start gap-3.5">
                          <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary transition-transform group-hover:scale-105 [&>svg]:h-[22px] [&>svg]:w-[22px]">
                            <IconFolder />
                          </span>
                          <span className="min-w-0 flex-1 pt-0.5">
                            <span className="block truncate font-display text-base font-bold text-heading">{sp.name}</span>
                            <span className="mt-0.5 block text-xs text-muted">{count} project{count === 1 ? '' : 's'}</span>
                          </span>
                          <span className="flex shrink-0 items-center gap-0.5 opacity-100 transition-opacity focus-within:opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
                            <button type="button" className={iconBtn} title="Rename space" aria-label={`Rename space ${sp.name}`} onClick={() => { setEditingSpace(sp.id); setEditSpaceName(sp.name); }}>
                              <IconPencil size={16} />
                            </button>
                            <button type="button" className={`${iconBtn} hover:!text-danger`} title="Delete space" aria-label={`Delete space ${sp.name}`} onClick={() => askDeleteSpace(sp)}>
                              <IconTrash size={16} />
                            </button>
                          </span>
                        </div>
                        <div className="flex items-center justify-between border-t border-line pt-3.5">
                          <span className="text-xs text-muted">
                            {count === 0 ? 'Empty space — add your first project' : `${count} project${count === 1 ? '' : 's'} inside`}
                          </span>
                          <button
                            type="button"
                            onClick={() => navigate(`/spaces?space=${sp.id}`)}
                            aria-label={`Open space ${sp.name}`}
                            className="inline-flex min-h-9 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-semibold text-primary hover:bg-primary-soft [&>svg]:h-[18px] [&>svg]:w-[18px]"
                          >
                            Open Space <IconArrowRight size={18} />
                          </button>
                        </div>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </>
      )}

      <ConfirmModal
        open={!!confirm}
        title={confirm?.title}
        message={confirm?.message}
        onConfirm={confirm?.onConfirm}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
