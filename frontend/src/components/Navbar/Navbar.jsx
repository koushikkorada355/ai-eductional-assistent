import { useEffect, useRef, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { logout } from '../../features/auth/authSlice.js';
import { fetchMe } from '../../features/auth/authApi.js';
import { tabFromLocation } from '../../pages/ProjectWorkspace/tabs.js';

/* Slim contextual header — NOT a second navbar. Brand + section navigation
 * live in the left sidebar; this bar carries location context + account only. */
function useCrumbs() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { spaceId, projectId } = useParams();
  const { spaces, projectsBySpace } = useSelector((s) => s.spaceProject);
  const path = location.pathname;
  if (path === '/analytics') return ['Global Analytics'];
  if (path === '/admin') return ['Admin'];
  if (path === '/spaces') {
    const sp = spaces.find((s) => s.id === searchParams.get('space'));
    return sp ? ['Spaces', sp.name] : ['Spaces'];
  }
  if (spaceId && projectId) {
    const space = spaces.find((s) => s.id === spaceId);
    const project = (projectsBySpace[spaceId] || []).find((p) => p.id === projectId);
    const section = tabFromLocation(path, searchParams);
    return [space?.name || 'Space', project?.name || 'Project', section];
  }
  return ['Spaces'];
}

export default function Navbar({ onMenuToggle }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const token = useSelector((s) => s.auth.token);
  const [open, setOpen] = useState(false);
  const [me, setMe] = useState(null);
  const menuRef = useRef(null);
  const crumbs = useCrumbs();

  useEffect(() => {
    if (token) fetchMe().then(setMe).catch(() => setMe(null));
    else setMe(null);
  }, [token]);
  // Close the profile menu on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);
  const onLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
      <button
        type="button"
        onClick={onMenuToggle}
        aria-label="Open navigation"
        className="hidden h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-heading max-lg:inline-flex"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
        {crumbs.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-1.5">
            {i > 0 && <span className="text-line" aria-hidden="true">/</span>}
            <span className={i === crumbs.length - 1 ? 'truncate font-display font-semibold text-heading' : 'hidden shrink-0 text-muted sm:inline'}>
              {c}
            </span>
          </span>
        ))}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        <div className="relative" ref={menuRef}>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={open}
            aria-label="Profile menu"
            className="inline-flex min-h-8 items-center gap-2 rounded-md py-0 pl-1 pr-2 text-[13px] font-medium text-ink hover:bg-canvas"
          >
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-primary font-display text-[13px] font-semibold text-white">
              {((me?.email || 'U')[0] || 'U').toUpperCase()}
            </span>
            <span className="max-w-[160px] truncate max-sm:hidden" title={me?.email || ''}>
              {me?.email || 'Profile'}
            </span>
          </button>
          <AnimatePresence>
            {open && (
              <motion.div
                role="menu"
                initial={{ opacity: 0, y: -6, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -6, scale: 0.98 }}
                transition={{ duration: 0.15 }}
                className="absolute right-0 top-[calc(100%+8px)] z-50 min-w-[160px] rounded-card border border-line bg-surface p-1 shadow-lg"
              >
                <button
                  type="button"
                  onClick={onLogout}
                  className="block w-full rounded-md px-3 py-2 text-left text-[13px] text-ink hover:bg-canvas"
                >
                  Logout
                </button>
                {me?.role === 'admin' && (
                  <button
                    type="button"
                    onClick={() => { setOpen(false); navigate('/admin'); }}
                    className="block w-full rounded-md px-3 py-2 text-left text-[13px] text-ink hover:bg-canvas"
                  >
                    Admin Dashboard
                  </button>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </header>
  );
}
