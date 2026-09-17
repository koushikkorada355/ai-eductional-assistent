import {
  IconFolder, IconBook, IconChat, IconTarget, IconFile, IconChart,
} from '../../components/icons/Icons.jsx';

/* Project sections. `param` is the ?tab= URL value; the tutor has its own
 * routes instead of a tab param so conversations stay deep-linkable. */
export const TABS = [
  { id: 'Materials', param: 'materials', Icon: IconFolder },
  { id: 'Concepts', param: 'concepts', Icon: IconBook },
  { id: 'AI Tutor', param: null, Icon: IconChat },
  { id: 'Quiz', param: 'quiz', Icon: IconTarget },
  { id: 'Assignments', param: 'assignments', Icon: IconFile },
  { id: 'Analytics', param: 'analytics', Icon: IconChart },
];

export const tabFromLocation = (pathname, searchParams) => {
  if (pathname.includes('/tutor')) return 'AI Tutor';
  const param = searchParams.get('tab');
  return TABS.find((t) => t.param === param)?.id || 'Materials';
};

export const projectBase = (spaceId, projectId) => `/spaces/${spaceId}/projects/${projectId}`;
export const tutorBase = (spaceId, projectId) => `${projectBase(spaceId, projectId)}/tutor`;

export const tabHref = (tabId, spaceId, projectId) => {
  if (tabId === 'AI Tutor') return tutorBase(spaceId, projectId);
  const tab = TABS.find((t) => t.id === tabId);
  const base = projectBase(spaceId, projectId);
  return tab?.param ? `${base}?tab=${tab.param}` : base;
};
