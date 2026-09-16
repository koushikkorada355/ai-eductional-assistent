import api from '../../api/client.js';

export const loginUser = (payload) => api.post('/auth/login', payload).then((r) => r.data);
export const registerUser = (payload) => api.post('/auth/register', payload).then((r) => r.data);
