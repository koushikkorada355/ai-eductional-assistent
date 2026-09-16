import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { askTutor, fetchMessages } from './tutorApi.js';

export const sendQuestion = createAsyncThunk('tutor/sendQuestion', async ({ spaceId, projectId, question }, { rejectWithValue }) => {
  try { return await askTutor(spaceId, projectId, question); } catch (e) { return rejectWithValue('Tutor request failed'); }
});
export const loadMessages = createAsyncThunk('tutor/loadMessages', async ({ spaceId, projectId }, { rejectWithValue }) => {
  try { return await fetchMessages(spaceId, projectId); } catch (e) { return rejectWithValue('Failed to load messages'); }
});

const slice = createSlice({
  name: 'tutor',
  initialState: { messages: [], status: 'idle', error: null },
  reducers: {
    pushUser(state, a) { state.messages.push({ role: 'user', content: a.payload }); },
    clearTutor(state) { state.messages = []; },
  },
  extraReducers: (b) => {
    b.addCase(loadMessages.fulfilled, (s, a) => { s.messages = a.payload; })
      .addCase(sendQuestion.pending, (s) => { s.status = 'loading'; })
      .addCase(sendQuestion.fulfilled, (s, a) => {
        s.status = 'succeeded';
        s.messages.push({ role: 'assistant', content: a.payload.answer, citations: a.payload.citations || [] });
      })
      .addCase(sendQuestion.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload; });
  },
});

export const { pushUser, clearTutor } = slice.actions;
export default slice.reducer;
