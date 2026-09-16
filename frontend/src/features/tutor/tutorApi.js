import api from '../../api/client.js';

export const askTutor = (spaceId, projectId, question) =>
  api.post(`/spaces/${spaceId}/projects/${projectId}/tutor`, { question }).then((r) => r.data);
export const fetchMessages = (spaceId, projectId) =>
  api.get(`/spaces/${spaceId}/projects/${projectId}/messages`).then((r) => r.data);
