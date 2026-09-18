import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../../api/client.js';
import { pageItems, pageMeta } from '../../utils/paging.js';

// API functions
const fetchAssignments = (spaceId, projectId, params) => api.get(`/spaces/${spaceId}/projects/${projectId}/assignments`, { params: params || {} }).then((r) => r.data);
const createAssignment = (spaceId, projectId, data) => api.post(`/spaces/${spaceId}/projects/${projectId}/assignments`, data).then((r) => r.data);
const getAssignment = (spaceId, projectId, assignmentId) => api.get(`/spaces/${spaceId}/projects/${projectId}/assignments/${assignmentId}`).then((r) => r.data);
const submitAssignment = (spaceId, projectId, assignmentId, data) => api.post(`/spaces/${spaceId}/projects/${projectId}/assignments/${assignmentId}/submit`, data).then((r) => r.data);

const serverMessage = (e, fallback) => e?.response?.data?.detail || fallback;

// Async thunks
export const loadAssignments = createAsyncThunk('assignments/loadAssignments', async ({ spaceId, projectId, page, pageSize }, { rejectWithValue }) => {
  try { return await fetchAssignments(spaceId, projectId, { page: page || 1, page_size: pageSize || 10 }); } catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load assignments')); }
});

export const createAssignmentThunk = createAsyncThunk('assignments/createAssignment', async ({ spaceId, projectId, conceptIds, numQuestions, title }, { rejectWithValue }) => {
  try {
    return await createAssignment(spaceId, projectId, {
      concept_ids: conceptIds,
      num_questions: numQuestions || 5,
      title: title || undefined,
    });
  } catch (e) { return rejectWithValue(serverMessage(e, 'Failed to create assignment')); }
});

export const loadAssignment = createAsyncThunk('assignments/loadAssignment', async ({ spaceId, projectId, assignmentId }, { rejectWithValue }) => {
  try { return await getAssignment(spaceId, projectId, assignmentId); } catch (e) { return rejectWithValue(serverMessage(e, 'Failed to load assignment')); }
});

export const submitAssignmentThunk = createAsyncThunk('assignments/submitAssignment', async ({ spaceId, projectId, assignmentId, answers }, { rejectWithValue }) => {
  try { return await submitAssignment(spaceId, projectId, assignmentId, { answers }); } catch (e) { return rejectWithValue(serverMessage(e, 'Failed to submit assignment')); }
});

const slice = createSlice({
  name: 'assignments',
  initialState: {
    assignments: [],
    assignmentsMeta: { total: 0, page: 1, pageSize: 10, pages: 0 },
    assignmentsSummary: null,
    selectedAssignment: null,
    status: 'idle',
    error: null,
  },
  reducers: {
    clearSelected(state) { state.selectedAssignment = null; state.status = 'idle'; state.error = null; },
    setAssignment(state, action) { state.selectedAssignment = action.payload; },
  },
  extraReducers: (builder) => {
    builder
      .addCase(loadAssignments.fulfilled, (state, action) => { state.assignments = pageItems(action.payload); state.assignmentsMeta = pageMeta(action.payload); state.assignmentsSummary = action.payload?.summary || null; state.error = null; })
      .addCase(createAssignmentThunk.pending, (state) => { state.status = 'loading'; state.error = null; })
      .addCase(createAssignmentThunk.fulfilled, (state, action) => {
        state.assignments.unshift({
          id: action.payload.id,
          project_id: action.payload.project_id,
          title: action.payload.title,
          status: action.payload.status,
          num_questions: (action.payload.questions || []).length,
          total: null,
          score: null,
          created_at: action.payload.created_at,
        });
        state.selectedAssignment = action.payload;
        state.status = 'idle';
        state.error = null;
      })
      .addCase(createAssignmentThunk.rejected, (state, action) => { state.status = 'idle'; state.error = action.payload; })
      .addCase(loadAssignment.fulfilled, (state, action) => {
        state.selectedAssignment = action.payload;
        state.status = 'idle';
        state.error = null;
        // Keep the list row in sync while polling generation/evaluation.
        state.assignments = state.assignments.map((a) =>
          a.id === action.payload.id
            ? {
                ...a,
                status: action.payload.status,
                num_questions: (action.payload.questions || []).length || a.num_questions,
                score: action.payload.score,
                total: action.payload.total,
              }
            : a
        );
      })
      .addCase(loadAssignment.pending, (state) => { state.status = 'loading'; })
      .addCase(loadAssignment.rejected, (state, action) => { state.status = 'idle'; state.error = action.payload; })
      .addCase(submitAssignmentThunk.pending, (state) => { state.status = 'loading'; state.error = null; })
      .addCase(submitAssignmentThunk.fulfilled, (state, action) => {
        // Submit returns the evaluating detail; polling fills in the grade.
        state.selectedAssignment = action.payload;
        state.assignments = state.assignments.map((a) =>
          a.id === action.payload.id
            ? { ...a, status: action.payload.status }
            : a
        );
        state.status = 'idle';
        state.error = null;
      })
      .addCase(submitAssignmentThunk.rejected, (state, action) => { state.status = 'idle'; state.error = action.payload; })
      .addMatcher((action) => action.type.endsWith('/rejected') && !action.payload, (state, action) => { state.error = action.error?.message || 'An error occurred'; });
  },
});

export const { clearSelected, setAssignment } = slice.actions;
export default slice.reducer;
