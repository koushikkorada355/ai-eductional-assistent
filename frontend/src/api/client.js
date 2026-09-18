import axios from 'axios';

const getBaseURL = () => {
  // Production override wins (Vercel: VITE_API_BASE_URL=https://<railway>/api/v1).
  // Vite bakes this in at build time — must be set in Vercel dashboard or
  // frontend/.env.production, otherwise Vercel previews would wrongly try
  // http://<vercel-host>:8000.
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    return envUrl;
  }
  // Local dev fallback: when accessed via LAN IP (e.g. friend opens
  // http://10.0.4.205:5173), call the backend on that same host.
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
      return `http://${host}:8000/api/v1`;
    }
  }
  return 'http://localhost:8000/api/v1';
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
