import api from '../../api/client.js';

const base = (spaceId, projectId) => `/spaces/${spaceId}/projects/${projectId}`;

// Turn an axios failure into a short, user-friendly message. Technical
// detail stays in devtools (console.error) — the learner never sees
// server, network, or infrastructure wording.
export function describeApiError(e, action) {
  const status = e?.response?.status;
  const detail = e?.response?.data?.detail;
  const detailText = Array.isArray(detail)
    ? detail.map((d) => d?.msg).filter(Boolean).join('; ')
    : (typeof detail === 'string' ? detail : null);
  if (typeof navigator !== 'undefined' && navigator !== null) {
    // Full error stays available in devtools for deeper diagnosis.
    // eslint-disable-next-line no-console
    console.error(`[tutor] ${action} failed:`, status ?? 'no-response', e?.response?.data ?? e?.message);
  }
  if (!status) {
    return `Couldn't complete that right now. Please check your connection and try again.`;
  }
  if (status === 404) {
    return `That isn't available right now. Please try again later.`;
  }
  if (status === 401 || status === 403) {
    return `Your session has expired. Please log in again.`;
  }
  if (status === 422) {
    return detailText ? `Invalid request: ${detailText}` : `Please check your input and try again.`;
  }
  if (status === 429) {
    return detailText || `You're doing that a bit too often. Please wait a moment and try again.`;
  }
  if (status >= 500) {
    return `Something went wrong while trying to ${action}. Please try again in a moment.`;
  }
  return detailText || `Couldn't complete that. Please try again.`;
}

export const listConversations = (spaceId, projectId, params) =>
  api.get(`${base(spaceId, projectId)}/conversations`, { params: params || {} }).then((r) => r.data);

export const createConversation = (spaceId, projectId, title) =>
  api.post(`${base(spaceId, projectId)}/conversations`, title ? { title } : {}).then((r) => r.data);

export const renameConversation = (spaceId, projectId, conversationId, title) =>
  api.patch(`${base(spaceId, projectId)}/conversations/${conversationId}`, { title }).then((r) => r.data);

export const deleteConversation = (spaceId, projectId, conversationId) =>
  api.delete(`${base(spaceId, projectId)}/conversations/${conversationId}`).then((r) => r.data);

export const fetchConversationMessages = (spaceId, projectId, conversationId) =>
  api.get(`${base(spaceId, projectId)}/conversations/${conversationId}/messages`).then((r) => r.data);

export const askTutorInConversation = (spaceId, projectId, conversationId, question, action) =>
  api.post(
    `${base(spaceId, projectId)}/conversations/${conversationId}/tutor`,
    action ? { question, action } : { question },
  ).then((r) => r.data);

// Legacy single-session endpoints (kept for backward compatibility).
export const askTutor = (spaceId, projectId, question) =>
  api.post(`${base(spaceId, projectId)}/tutor`, { question }).then((r) => r.data);
export const fetchMessages = (spaceId, projectId) =>
  api.get(`${base(spaceId, projectId)}/messages`).then((r) => r.data);
