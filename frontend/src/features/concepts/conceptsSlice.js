import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../api/client.js';

const fetchConcepts = (spaceId, projectId) =>
  api.get(`/spaces/${spaceId}/projects/${projectId}/concepts`).then((r) => r.data);

const serverMessage = (e, fallback) => e?.response?.data?.detail || fallback;

export const loadConcepts = createAsyncThunk(
  'concepts/loadConcepts',
  async ({ spaceId, projectId }, { rejectWithValue }) => {
    try {
      return await fetchConcepts(spaceId, projectId);
    } catch (e) {
      return rejectWithValue(serverMessage(e, 'Failed to load concepts'));
    }
  }
);

const slice = createSlice({
  name: 'concepts',
  initialState: {
    concepts: [],
    status: 'idle',
    error: null,
  },
  reducers: {},
  extraReducers: (builder) => {
    builder
      .addCase(loadConcepts.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(loadConcepts.fulfilled, (state, action) => {
        state.concepts = action.payload || [];
        state.status = 'idle';
        state.error = null;
      })
      .addCase(loadConcepts.rejected, (state, action) => {
        state.status = 'idle';
        state.error = action.payload || 'Failed to load concepts';
      });
  },
});

export default slice.reducer;
