import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { createQuiz, saveAnswer, submitQuiz, fetchAttempts, fetchQuizDetail } from './quizApi.js';

export const startQuiz = createAsyncThunk('quiz/start', async ({ projectId, name, goal, numMcq, numOpen }, { rejectWithValue }) => {
  try { return await createQuiz(projectId, { name, goal: goal || '', num_mcq: numMcq ?? 3, num_open: numOpen ?? 2 }); } catch (e) { return rejectWithValue(e.response?.data?.detail || 'Failed to create quiz'); }
});
export const refreshQuiz = createAsyncThunk('quiz/refresh', async ({ quizId }, { rejectWithValue }) => {
  try { return await fetchQuizDetail(quizId); } catch (e) { return rejectWithValue('Failed to load quiz'); }
});
export const persistAnswer = createAsyncThunk(
  'quiz/save',
  async ({ quizId, questionId, answer }, { rejectWithValue }) => {
    try { return await saveAnswer(quizId, questionId, answer); } catch (e) { return rejectWithValue(e.response?.data?.detail || 'Failed to save answer'); }
  }
);
export const submitFullQuiz = createAsyncThunk('quiz/submit', async ({ quizId }, { rejectWithValue }) => {
  try { return await submitQuiz(quizId); } catch (e) { return rejectWithValue(e.response?.data?.detail || 'Failed to submit quiz'); }
});
export const loadAttempts = createAsyncThunk('quiz/attempts', async ({ projectId }, { rejectWithValue }) => {
  try { return await fetchAttempts(projectId); } catch (e) { return rejectWithValue('Failed to load attempts'); }
});
export const loadQuizDetail = createAsyncThunk('quiz/detail', async ({ quizId }, { rejectWithValue }) => {
  try { return await fetchQuizDetail(quizId); } catch (e) { return rejectWithValue('Failed to load quiz details'); }
});
export const viewAttempt = createAsyncThunk('quiz/viewAttempt', async ({ quizId }, { rejectWithValue }) => {
  try { return await fetchQuizDetail(quizId); } catch (e) { return rejectWithValue('Failed to load quiz details'); }
});
export const resumeAttempt = createAsyncThunk('quiz/resume', async ({ quizId }, { rejectWithValue }) => {
  try { return await fetchQuizDetail(quizId); } catch (e) { return rejectWithValue('Failed to load quiz details'); }
});

const slice = createSlice({
  name: 'quiz',
  initialState: {
    view: 'start',
    quizId: null,
    name: '',
    goal: '',
    questions: [],
    index: 0,
    drafts: {},
    attempts: [],
    detail: null,
    average: null,
    status: 'idle',
    error: null,
  },
  reducers: {
    resetQuiz(state) {
      state.view = 'start';
      state.quizId = null;
      state.name = '';
      state.goal = '';
      state.questions = [];
      state.index = 0;
      state.drafts = {};
      state.detail = null;
      state.average = null;
      state.status = 'idle';
      state.error = null;
    },
    setIndex(state, a) { state.index = a.payload; },
    setDraft(state, a) { state.drafts[a.payload.id] = a.payload.value; },
    openResults(state, a) {
      state.detail = a.payload;
      state.average = a.payload.average_score;
      state.view = 'results';
      state.status = 'done';
    },
    backToStart(state) {
      state.view = 'start';
      state.quizId = null;
      state.questions = [];
      state.index = 0;
      state.drafts = {};
      state.detail = null;
      state.average = null;
      state.status = 'idle';
      state.error = null;
    },
  },
  extraReducers: (b) => {
    b.addCase(startQuiz.pending, (s) => { s.status = 'creating'; s.error = null; })
      .addCase(startQuiz.fulfilled, (s, a) => {
        s.quizId = a.payload.quiz_id;
        s.name = a.payload.name;
        s.view = 'generating';
        s.status = 'generating';
      })
      .addCase(startQuiz.rejected, (s, a) => { s.status = 'idle'; s.error = a.payload; })
      .addCase(refreshQuiz.fulfilled, (s, a) => {
        const d = a.payload;
        if (d.status === 'in_progress' && s.view === 'generating') {
          s.questions = d.questions;
          s.index = 0;
          s.drafts = Object.fromEntries(d.questions.map((q) => [q.id, q.user_answer || '']));
          s.view = 'active';
          s.status = 'active';
        } else if (d.status === 'failed') {
          s.view = 'start';
          s.status = 'idle';
          s.error = 'Quiz generation failed. Please try again.';
        } else if (d.status === 'completed') {
          s.questions = d.questions;
          s.average = d.average_score;
          s.view = 'results';
          s.status = 'done';
        }
      })
      .addCase(refreshQuiz.rejected, (s, a) => { s.error = a.payload; })
      .addCase(persistAnswer.fulfilled, (s, a) => {
        s.questions = s.questions.map((q) => (q.id === a.payload.id ? { ...q, user_answer: a.payload.user_answer } : q));
        s.status = 'active';
      })
      .addCase(persistAnswer.rejected, (s, a) => { s.error = a.payload; })
      .addCase(submitFullQuiz.fulfilled, (s) => { s.view = 'evaluating'; s.status = 'evaluating'; })
      .addCase(submitFullQuiz.rejected, (s, a) => { s.error = a.payload; })
      .addCase(loadAttempts.fulfilled, (s, a) => { s.attempts = a.payload; })
      .addCase(loadQuizDetail.fulfilled, (s, a) => { s.detail = a.payload; })
      .addCase(viewAttempt.fulfilled, (s, a) => {
        s.questions = a.payload.questions;
        s.name = a.payload.name;
        s.average = a.payload.average_score;
        s.quizId = a.payload.id;
        s.view = 'results';
        s.status = 'done';
      })
      .addCase(viewAttempt.rejected, (s, a) => { s.error = a.payload; })
      .addCase(resumeAttempt.pending, (s) => { s.status = 'loading'; s.error = null; })
      .addCase(resumeAttempt.fulfilled, (s, a) => {
        const d = a.payload;
        s.quizId = d.id;
        s.name = d.name;
        s.questions = d.questions || [];
        s.index = 0;
        s.drafts = Object.fromEntries((d.questions || []).map((q) => [q.id, q.user_answer || '']));
        s.average = d.average_score;
        if (d.status === 'completed') {
          s.view = 'results';
          s.status = 'done';
        } else if (d.status === 'in_progress') {
          s.view = 'active';
          s.status = 'active';
        } else if (d.status === 'evaluating') {
          s.view = 'evaluating';
          s.status = 'evaluating';
        } else if (d.status === 'failed') {
          s.view = 'start';
          s.status = 'idle';
          s.error = 'Quiz generation failed. Please try again.';
        } else {
          s.view = 'generating';
          s.status = 'generating';
        }
      })
      .addCase(resumeAttempt.rejected, (s, a) => { s.status = 'idle'; s.error = a.payload; });
  },
});

export const { resetQuiz, setIndex, setDraft, openResults, backToStart } = slice.actions;
export default slice.reducer;
