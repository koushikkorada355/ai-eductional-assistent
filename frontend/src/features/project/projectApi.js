import api from '../../api/client.js';

export const fetchSpaces = () => api.get('/spaces/').then((r) => r.data);
export const createSpace = (payload) => api.post('/spaces/', payload).then((r) => r.data);
export const updateSpace = (spaceId, payload) => api.put(`/spaces/${spaceId}`, payload).then((r) => r.data);
export const deleteSpace = (spaceId) => api.delete(`/spaces/${spaceId}`).then((r) => r.data);
export const fetchProjects = (spaceId) => api.get(`/spaces/${spaceId}/projects/`).then((r) => r.data);
export const createProject = (spaceId, payload) => api.post(`/spaces/${spaceId}/projects/`, payload).then((r) => r.data);
export const updateProject = (spaceId, projectId, payload) =>
  api.put(`/spaces/${spaceId}/projects/${projectId}`, payload).then((r) => r.data);
export const deleteProject = (spaceId, projectId) =>
  api.delete(`/spaces/${spaceId}/projects/${projectId}`).then((r) => r.data);
export const uploadPdf = (spaceId, projectId, file) => {
  const form = new FormData();
  form.append('file', file);
  return api.post(`/spaces/${spaceId}/projects/${projectId}/upload-pdf`, form).then((r) => r.data);
};
export const fetchDocuments = (spaceId, projectId) => api.get(`/spaces/${spaceId}/projects/${projectId}/documents`).then((r) => r.data);
export const fetchEvidence = (spaceId, projectId, documentId) =>
  api.get(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}/evidence`).then((r) => r.data);
export const retryDocument = (spaceId, projectId, documentId) =>
  api.post(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}/retry`).then((r) => r.data);
export const deleteDocument = (spaceId, projectId, documentId) =>
  api.delete(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}`).then((r) => r.data);
