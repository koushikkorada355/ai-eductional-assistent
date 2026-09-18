import api from '../../api/client.js';

export const fetchSpaces = (params) => api.get('/spaces/', { params: params || {} }).then((r) => r.data);
export const createSpace = (payload) => api.post('/spaces/', payload).then((r) => r.data);
export const updateSpace = (spaceId, payload) => api.put(`/spaces/${spaceId}`, payload).then((r) => r.data);
export const deleteSpace = (spaceId) => api.delete(`/spaces/${spaceId}`).then((r) => r.data);
export const fetchProjects = (spaceId, params) => api.get(`/spaces/${spaceId}/projects/`, { params: params || {} }).then((r) => r.data);
export const createProject = (spaceId, payload) => api.post(`/spaces/${spaceId}/projects/`, payload).then((r) => r.data);
export const updateProject = (spaceId, projectId, payload) =>
  api.put(`/spaces/${spaceId}/projects/${projectId}`, payload).then((r) => r.data);
export const deleteProject = (spaceId, projectId) =>
  api.delete(`/spaces/${spaceId}/projects/${projectId}`).then((r) => r.data);
export const uploadPdf = (spaceId, projectId, file) => {
  const form = new FormData();
  form.append('file', file, file?.name || 'upload.pdf');
  // Let the browser set the multipart boundary; 120s timeout for large PDFs on Railway.
  return api.post(`/spaces/${spaceId}/projects/${projectId}/upload-pdf`, form, { timeout: 120000 }).then((r) => r.data);
};
export const fetchDocuments = (spaceId, projectId, params) => api.get(`/spaces/${spaceId}/projects/${projectId}/documents`, { params: params || {} }).then((r) => r.data);
export const fetchEvidence = (spaceId, projectId, documentId) =>
  api.get(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}/evidence`).then((r) => r.data);
export const retryDocument = (spaceId, projectId, documentId) =>
  api.post(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}/retry`).then((r) => r.data);
export const deleteDocument = (spaceId, projectId, documentId) =>
  api.delete(`/spaces/${spaceId}/projects/${projectId}/documents/${documentId}`).then((r) => r.data);
