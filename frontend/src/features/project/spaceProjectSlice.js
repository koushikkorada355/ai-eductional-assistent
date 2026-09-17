import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import {
  fetchSpaces, createSpace, updateSpace, deleteSpace,
  fetchProjects, createProject, updateProject, deleteProject,
  uploadPdf, fetchDocuments, retryDocument as retryDocumentApi, deleteDocument as deleteDocumentApi,
} from './projectApi.js';

export const loadSpaces = createAsyncThunk('spaceProject/loadSpaces', async (_, { rejectWithValue }) => {
  try { return await fetchSpaces(); } catch (e) { return rejectWithValue('Failed to load spaces'); }
});
export const addSpace = createAsyncThunk('spaceProject/addSpace', async (payload, { rejectWithValue }) => {
  try { return await createSpace(payload); } catch (e) { return rejectWithValue('Failed to create space'); }
});
export const loadProjects = createAsyncThunk('spaceProject/loadProjects', async (spaceId, { rejectWithValue }) => {
  try {
    const data = await fetchProjects(spaceId);
    return { spaceId, data };
  } catch (e) { return rejectWithValue('Failed to load projects'); }
});
export const addProject = createAsyncThunk('spaceProject/addProject', async ({ spaceId, payload }, { rejectWithValue }) => {
  try { return await createProject(spaceId, payload); } catch (e) { return rejectWithValue('Failed to create project'); }
});
export const editSpace = createAsyncThunk('spaceProject/editSpace', async ({ spaceId, payload }, { rejectWithValue }) => {
  try { return await updateSpace(spaceId, payload); } catch (e) { return rejectWithValue('Failed to update space'); }
});
export const removeSpace = createAsyncThunk('spaceProject/removeSpace', async ({ spaceId }, { rejectWithValue }) => {
  try { await deleteSpace(spaceId); return { spaceId }; } catch (e) { return rejectWithValue('Failed to delete space'); }
});
export const editProject = createAsyncThunk('spaceProject/editProject', async ({ spaceId, projectId, payload }, { rejectWithValue }) => {
  try { return await updateProject(spaceId, projectId, payload); } catch (e) { return rejectWithValue('Failed to update project'); }
});
export const removeProject = createAsyncThunk('spaceProject/removeProject', async ({ spaceId, projectId }, { rejectWithValue }) => {
  try { await deleteProject(spaceId, projectId); return { spaceId, projectId }; } catch (e) { return rejectWithValue('Failed to delete project'); }
});
export const uploadDocument = createAsyncThunk('spaceProject/uploadDocument', async ({ spaceId, projectId, file }, { rejectWithValue }) => {
  try { return await uploadPdf(spaceId, projectId, file); } catch (e) { return rejectWithValue(e.response?.data?.detail || 'PDF upload failed'); }
});
export const loadDocuments = createAsyncThunk('spaceProject/loadDocuments', async ({ spaceId, projectId }, { rejectWithValue }) => {
  try { return await fetchDocuments(spaceId, projectId); } catch (e) { return rejectWithValue('Failed to load documents'); }
});
export const retryDocument = createAsyncThunk('spaceProject/retryDocument', async ({ spaceId, projectId, documentId }, { rejectWithValue }) => {
  try { return await retryDocumentApi(spaceId, projectId, documentId); } catch (e) { return rejectWithValue(e.response?.data?.detail || 'Failed to retry document'); }
});
export const removeDocument = createAsyncThunk('spaceProject/removeDocument', async ({ spaceId, projectId, documentId }, { rejectWithValue }) => {
  try { await deleteDocumentApi(spaceId, projectId, documentId); return { documentId }; } catch (e) { return rejectWithValue(e.response?.data?.detail || 'Failed to delete document'); }
});

const slice = createSlice({
  name: 'spaceProject',
  initialState: {
    spaces: [],
    projectsBySpace: {},
    documents: [],
    selectedSpaceId: null,
    selectedProjectId: null,
    status: 'idle',
    error: null,
  },
  reducers: {
    selectSpace(state, a) { state.selectedSpaceId = a.payload; },
    selectProject(state, a) { state.selectedProjectId = a.payload; },
  },
  extraReducers: (b) => {
    b.addCase(loadSpaces.fulfilled, (s, a) => { s.spaces = a.payload; })
      .addCase(addSpace.fulfilled, (s, a) => { s.spaces.unshift(a.payload); })
      .addCase(loadProjects.fulfilled, (s, a) => { s.projectsBySpace[a.payload.spaceId] = a.payload.data; })
      .addCase(addProject.fulfilled, (s, a) => {
        const sid = a.payload.space_id;
        if (!s.projectsBySpace[sid]) s.projectsBySpace[sid] = [];
        s.projectsBySpace[sid].unshift(a.payload);
      })
      .addCase(editSpace.fulfilled, (s, a) => {
        s.spaces = s.spaces.map((sp) => (sp.id === a.payload.id ? a.payload : sp));
      })
      .addCase(removeSpace.fulfilled, (s, a) => {
        s.spaces = s.spaces.filter((sp) => sp.id !== a.payload.spaceId);
        delete s.projectsBySpace[a.payload.spaceId];
      })
      .addCase(editProject.fulfilled, (s, a) => {
        const sid = a.payload.space_id;
        s.projectsBySpace[sid] = (s.projectsBySpace[sid] || []).map((p) => (p.id === a.payload.id ? a.payload : p));
      })
      .addCase(removeProject.fulfilled, (s, a) => {
        const sid = a.payload.spaceId;
        s.projectsBySpace[sid] = (s.projectsBySpace[sid] || []).filter((p) => p.id !== a.payload.projectId);
      })
      .addCase(uploadDocument.fulfilled, (s, a) => { s.documents.unshift(a.payload); })
      .addCase(loadDocuments.fulfilled, (s, a) => { s.documents = a.payload; })
      .addCase(retryDocument.fulfilled, (s, a) => {
        s.documents = s.documents.map((d) => (d.id === a.payload.id ? a.payload : d));
      })
      .addCase(removeDocument.fulfilled, (s, a) => {
        s.documents = s.documents.filter((d) => d.id !== a.payload.documentId);
      })
      .addMatcher((ac) => ac.type.endsWith('/rejected'), (s, a) => { s.error = a.payload; });
  },
});

export const { selectSpace, selectProject } = slice.actions;
export default slice.reducer;
