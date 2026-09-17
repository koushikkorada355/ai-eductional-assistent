import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate, useParams, useLocation, useSearchParams } from 'react-router-dom';
import { loadSpaces, loadProjects } from '../../features/project/spaceProjectSlice.js';
import { TABS, tabFromLocation, tabHref } from '../../pages/ProjectWorkspace/tabs.js';
import {
  IconX, IconChart, IconFolder, IconGraduation,
  IconPlus, IconArrowLeft,
} from '../icons/Icons.jsx';

/* Progressive drill-down navigation — one level at a time, never the whole
 * tree. Links and context only; all forms and management live in the
 * right workspace.
 * Level 0 (global): Spaces first, Global Analytics anchored bottom (+ Admin).
 * Level 1 (space, /spaces?space=ID): ← Spaces, space identity, Projects
 *   label, + Create Project. No project list — projects render in the
 *   workspace. No other spaces.
 * Level 2 (project routes): ← parent space, project identity, its 6
 *   feature links. Nothing else. */
const SECTION_ORDER = ['AI Tutor', 'Materials', 'Concepts', 'Quiz', 'Assignments', 'Analytics'];
const PROJECT_LINKS = SECTION_ORDER.map((id) => TABS.find((t) => t.id === id)).filter(Boolean);

function NavItem({ active, onClick, icon, label, badge, ariaLabel, primary }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? 'page' : undefined}
      aria-label={ariaLabel}
      className={`flex w-full items-center gap-2.5 rounded-md px-2.5 transition-colors ${
        primary ? 'py-2.5 text-[15px] font-semibold' : 'py-2 text-[13px] font-medium'
      } ${
        active
          ? 'bg-primary-soft font-semibold text-primary'
          : primary
            ? 'text-heading hover:bg-canvas hover:text-primary'
            : 'text-ink hover:bg-canvas hover:text-primary'
      }`}
    >
      <span className={`inline-flex shrink-0 ${primary ? '[&>svg]:h-[22px] [&>svg]:w-[22px]' : '[&>svg]:h-[18px] [&>svg]:w-[18px]'}`}>{icon}</span>
      <span className="flex-1 truncate text-left">{label}</span>
      {badge}
    </button>
  );
}

function BackLink({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={`Back to ${label}`}
      className="inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]"
    >
      <IconArrowLeft /> <span className="truncate">{label}</span>
    </button>
  );
}

function ContextCard({ avatar, title, subtitle, icon }) {
  return (
    <div className="flex items-center gap-2.5 rounded-md border border-line bg-canvas px-2.5 py-2" aria-current="true">
      <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary font-display text-[13px] font-bold uppercase text-white [&>svg]:h-4 [&>svg]:w-4">
        {icon || avatar}
      </span>
      <span className="min-w-0 flex-1 leading-tight">
        <span className="block truncate text-[13px] font-semibold text-heading">{title}</span>
        {subtitle && <span className="block truncate text-[11px] text-muted">{subtitle}</span>}
      </span>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <p className="px-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted">
      {children}
    </p>
  );
}

function CreateAction({ onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex min-h-9 w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-line bg-surface px-3 text-[13px] font-semibold text-primary transition-colors hover:border-primary hover:bg-primary-soft [&>svg]:h-4 [&>svg]:w-4"
    >
      <IconPlus size={16} /> {label}
    </button>
  );
}

export default function Sidebar({ open, onClose, isAdmin }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { spaceId, projectId } = useParams();
  const { spaces, projectsBySpace } = useSelector((s) => s.spaceProject);

  // Read-only directory data for navigation context (no forms here).
  useEffect(() => { dispatch(loadSpaces()); }, [dispatch]);
  useEffect(() => {
    spaces.forEach((sp) => dispatch(loadProjects(sp.id)));
  }, [dispatch, spaces.length]);

  const inProject = Boolean(spaceId && projectId);
  const onSpacesRoute = location.pathname === '/spaces';
  const selectedSpace = !inProject && onSpacesRoute
    ? spaces.find((s) => s.id === searchParams.get('space')) || null
    : null;
  const activeTab = inProject ? tabFromLocation(location.pathname, searchParams) : null;
  const project = inProject ? (projectsBySpace[spaceId] || []).find((p) => p.id === projectId) : null;
  const projectSpace = inProject ? spaces.find((s) => s.id === spaceId) : null;
  const spaceProjectCount = selectedSpace ? (projectsBySpace[selectedSpace.id] || []).length : 0;

  const go = (href) => {
    navigate(href);
    if (onClose) onClose();
  };

  const level = inProject ? 2 : selectedSpace ? 1 : 0;

  return (
    <aside
      className={`fixed bottom-0 left-0 top-0 z-50 flex w-[264px] shrink-0 -translate-x-full flex-col border-r border-line bg-surface transition-transform duration-200 lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
        open ? 'translate-x-0 shadow-lg' : ''
      }`}
      aria-label={level === 2 ? 'Project navigation' : level === 1 ? 'Space navigation' : 'Primary navigation'}
    >
      {open && (
        <div className="fixed inset-0 -z-10 bg-black/30 lg:hidden" onClick={onClose} aria-hidden="true" />
      )}

      {/* Brand */}
      <div className="flex shrink-0 items-center gap-2.5 border-b border-line px-4 py-3.5">
        <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary font-display text-[15px] font-bold text-white">
          A
        </span>
        <span className="min-w-0 flex-1 leading-tight">
          <span className="block truncate font-display text-[13px] font-bold text-heading">
            AI Study Companion
          </span>
          <span className="block truncate text-[11px] text-muted">Learn from your documents</span>
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close navigation"
          className="inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-ink lg:hidden [&>svg]:h-[13px] [&>svg]:w-[13px]"
        >
          <IconX />
        </button>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3 py-4">
        {level === 2 && (
          <>
            <BackLink onClick={() => go(`/spaces?space=${spaceId}`)} label={projectSpace?.name || 'Spaces'} />
            <div className="mt-1.5">
              <ContextCard avatar={(project?.name || '?')[0]} title={project?.name || 'Project'} subtitle={projectSpace?.name || 'Space'} />
            </div>
            <div className="mt-1.5 flex flex-col gap-0.5" role="list" aria-label="Project sections">
              {PROJECT_LINKS.map((t) => (
                <NavItem
                  key={t.id}
                  label={t.id}
                  icon={<t.Icon />}
                  active={activeTab === t.id}
                  onClick={() => go(tabHref(t.id, spaceId, projectId))}
                  badge={t.id === 'AI Tutor' ? (
                    <span className="inline-flex shrink-0 items-center rounded-full bg-primary-soft px-1.5 py-px text-[10px] font-bold text-primary">
                      AI
                    </span>
                  ) : undefined}
                />
              ))}
            </div>
          </>
        )}

        {level === 1 && (
          <>
            <BackLink onClick={() => go('/spaces')} label="Spaces" />
            <div className="mt-1.5">
              <ContextCard
                avatar={(selectedSpace.name || '?')[0]}
                title={selectedSpace.name}
                subtitle={`${spaceProjectCount} project${spaceProjectCount === 1 ? '' : 's'}`}
              />
            </div>
            <div className="mt-3 flex items-center justify-between px-2">
              <SectionLabel>Projects</SectionLabel>
            </div>
            <button
              type="button"
              onClick={() => go(`/spaces?space=${selectedSpace.id}`)}
              className="mt-1 rounded-md px-2 py-1 text-left text-xs text-muted hover:bg-canvas hover:text-ink"
            >
              View all projects in this space →
            </button>
            <div className="mt-2">
              <CreateAction onClick={() => go(`/spaces?space=${selectedSpace.id}&create=project`)} label="Create Project" />
            </div>
          </>
        )}

        {level === 0 && !onSpacesRoute && (
          <>
            {/* Spaces is the primary concept. Global Analytics is anchored
                to the bottom as a secondary destination — never an equal
                item beside Spaces. */}
            <NavItem
              primary
              label="Spaces"
              icon={<IconFolder />}
              active={false}
              onClick={() => go('/spaces')}
            />
            <div className="mt-auto flex flex-col gap-0.5 border-t border-line pt-2">
              {isAdmin && (
                <NavItem
                  label="Admin"
                  icon={<IconGraduation />}
                  active={location.pathname === '/admin'}
                  onClick={() => go('/admin')}
                />
              )}
              <NavItem
                label="Global Analytics"
                icon={<IconChart />}
                active={location.pathname === '/analytics'}
                onClick={() => go('/analytics')}
              />
            </div>
          </>
        )}

        {level === 0 && onSpacesRoute && (
          <>
            <div className="mt-1.5">
              <ContextCard icon={<IconFolder size={16} />} title="Spaces" subtitle="Manage learning spaces" />
            </div>
            <div className="mt-2">
              <CreateAction onClick={() => go('/spaces?create=space')} label="Create Space" />
            </div>
            <div className="mt-auto flex flex-col gap-0.5 border-t border-line pt-2">
              {isAdmin && (
                <NavItem
                  label="Admin"
                  icon={<IconGraduation />}
                  active={false}
                  onClick={() => go('/admin')}
                />
              )}
              <NavItem
                label="Global Analytics"
                icon={<IconChart />}
                active={false}
                onClick={() => go('/analytics')}
              />
            </div>
          </>
        )}
      </nav>
    </aside>
  );
}
