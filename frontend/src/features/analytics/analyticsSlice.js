import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../api/client.js';

const serverMessage = (e, fallback) => e?.response?.data?.detail || fallback;

export const loadOverview = createAsyncThunk('analytics/loadOverview', async (_, { rejectWithValue }) => {
  try { return (await api.get('/analytics/overview')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load analytics')); }
});

export const loadProjectAnalytics = createAsyncThunk(
  'analytics/loadProjectAnalytics',
  async ({ spaceId, projectId }, { rejectWithValue }) => {
    try { return (await api.get(`/spaces/${spaceId}/projects/${projectId}/analytics`)).data; }
    catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load project analytics')); }
  }
);

export const loadAdminOverview = createAsyncThunk('analytics/loadAdminOverview', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/overview')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load admin overview')); }
});

export const loadAdminUsers = createAsyncThunk('analytics/loadAdminUsers', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/users')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load users')); }
});

export const loadAdminJobs = createAsyncThunk('analytics/loadAdminJobs', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/jobs')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load jobs')); }
});

export const loadAdminEvaluations = createAsyncThunk('analytics/loadAdminEvaluations', async (params, { rejectWithValue }) => {
  try { return (await api.get('/admin/evaluations', { params: params || {} })).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load evaluations')); }
});

export const loadAdminUsage = createAsyncThunk('analytics/loadAdminUsage', async (params, { rejectWithValue }) => {
  try { return (await api.get('/admin/ai-usage', { params: params || {} })).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load AI usage')); }
});

export const loadAdminUserDetail = createAsyncThunk('analytics/loadAdminUserDetail', async (userId, { rejectWithValue }) => {
  try { return (await api.get(`/admin/users/${userId}`)).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load user detail')); }
});

export const loadAdminSpaces = createAsyncThunk('analytics/loadAdminSpaces', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/spaces')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load spaces')); }
});

export const loadAdminProjects = createAsyncThunk('analytics/loadAdminProjects', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/projects')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load projects')); }
});

export const loadAdminActivity = createAsyncThunk('analytics/loadAdminActivity', async (params, { rejectWithValue }) => {
  try { return (await api.get('/admin/activity', { params: params || {} })).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load activity')); }
});

export const loadAdminLearning = createAsyncThunk('analytics/loadAdminLearning', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/learning')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load learning analytics')); }
});

export const loadAdminHealth = createAsyncThunk('analytics/loadAdminHealth', async (_, { rejectWithValue }) => {
  try { return (await api.get('/admin/health')).data; }
  catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load system health')); }
});

const slice = createSlice({
  name: 'analytics',
  initialState: {
    overview: null,
    project: null,
    admin: {
      overview: null, users: [], userDetail: null, spaces: [], projects: [],
      activity: null, learning: null, jobs: [], jobSummary: null,
      evaluations: null, usage: null, health: null,
    },
    status: 'idle',
    error: null,
  },
  reducers: {
    clearProjectAnalytics(state) { state.project = null; },
  },
  extraReducers: (b) => {
    b.addCase(loadOverview.pending, (s) => { s.status = 'loading'; s.error = null; })
      .addCase(loadOverview.fulfilled, (s, a) => { s.overview = a.payload; s.status = 'idle'; })
      .addCase(loadOverview.rejected, (s, a) => { s.status = 'idle'; s.error = a.payload; })
      .addCase(loadProjectAnalytics.pending, (s) => { s.status = 'loading'; s.error = null; })
      .addCase(loadProjectAnalytics.fulfilled, (s, a) => { s.project = a.payload; s.status = 'idle'; })
      .addCase(loadProjectAnalytics.rejected, (s, a) => { s.status = 'idle'; s.error = a.payload; })
      .addCase(loadAdminOverview.fulfilled, (s, a) => { s.admin.overview = a.payload; })
      .addCase(loadAdminUsers.fulfilled, (s, a) => { s.admin.users = a.payload || []; })
      .addCase(loadAdminUserDetail.fulfilled, (s, a) => { s.admin.userDetail = a.payload; })
      .addCase(loadAdminSpaces.fulfilled, (s, a) => { s.admin.spaces = a.payload || []; })
      .addCase(loadAdminProjects.fulfilled, (s, a) => { s.admin.projects = a.payload || []; })
      .addCase(loadAdminActivity.fulfilled, (s, a) => { s.admin.activity = a.payload; })
      .addCase(loadAdminLearning.fulfilled, (s, a) => { s.admin.learning = a.payload; })
      .addCase(loadAdminHealth.fulfilled, (s, a) => { s.admin.health = a.payload; })
      .addCase(loadAdminJobs.fulfilled, (s, a) => {
        s.admin.jobs = a.payload?.items || a.payload || [];
        s.admin.jobSummary = a.payload?.summary || null;
      })
      .addCase(loadAdminEvaluations.fulfilled, (s, a) => { s.admin.evaluations = a.payload; })
      .addCase(loadAdminUsage.fulfilled, (s, a) => { s.admin.usage = a.payload; });
  },
});

export const { clearProjectAnalytics } = slice.actions;
export default slice.reducer;
