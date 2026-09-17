import api from '../../api/client.js';

const base = (spaceId, projectId) => `/spaces/${spaceId}/projects/${projectId}`;

// Turn an axios failure into a specific, actionable message so API problems
// are diagnosable from the UI instead of surfacing as generic "failed".
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
    return `Cannot reach the backend server while trying to ${action}. Check: 1) "docker compose ps" (is backend up?), 2) "curl -i http://localhost:8000/health" (does it return healthy?), 3) open the app at http://localhost:5173 (not 127.0.0.1).`;
  }
  if (status === 404) {
    return `Server has no conversation endpoints yet (404) — the backend is running old code. Restart it with: docker compose restart backend`;
  }
  if (status === 401 || status === 403) {
    return `Not authorized to ${action} (HTTP ${status}). Try logging in again.`;
  }
  if (status === 422) {
    return detailText ? `Invalid request: ${detailText}` : `The server rejected the request (422) while trying to ${action}.`;
  }
  if (status >= 500) {
    return `Server error (HTTP ${status}) while trying to ${action}. Check backend logs: docker compose logs backend${detailText ? ` — ${detailText}` : ''}`;
  }
  return detailText || `Failed to ${action} (HTTP ${status}).`;
}

export const listConversations = (spaceId, projectId) =>
  api.get(`${base(spaceId, projectId)}/conversations`).then((r) => r.data);

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
