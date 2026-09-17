import axios from 'axios';

const getBaseURL = () => {
  // When accessed via LAN IP (e.g. friend opens http://10.0.4.205:5173),
  // the browser must call the backend on that same host, not localhost.
  // So derive backend URL from window.location.hostname dynamically.
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:8000/api/v1`;
    }
  }
  return import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
};

const api = axios.create({
  baseURL: getBaseURL(),
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
