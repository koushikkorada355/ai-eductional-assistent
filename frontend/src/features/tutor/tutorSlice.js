import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import {
  listConversations,
  createConversation,
  renameConversation,
  deleteConversation,
  fetchConversationMessages,
  askTutorInConversation,
  describeApiError,
} from './tutorApi.js';
import { pageItems, pageMeta } from '../../utils/paging.js';

export function normalizeCitations(raw) {
  let list = raw;
  if (typeof list === 'string') {
    try { list = JSON.parse(list); } catch { return []; }
  }
  if (!Array.isArray(list)) return [];
  const out = [];
  const seen = new Set();
  for (const c of list) {
    if (!c || typeof c !== 'object') continue;
    const name = c.pdf_name ?? c.file_name ?? c.document_name ?? 'Document';
    const page = Number(c.page_number ?? c.page);
    if (!Number.isFinite(page)) continue;
    const excerpt = c.chunk_excerpt ?? c.excerpt ?? c.content ?? c.text ?? '';
    const key = `${String(name)}::${page}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ pdf_name: String(name), page_number: page, chunk_excerpt: String(excerpt || '') });
  }
  out.sort((a, b) => a.page_number - b.page_number || a.pdf_name.localeCompare(b.pdf_name));
  return out;
}

export function normalizeSuggestions(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  const seen = new Set();
  for (const item of raw) {
    if (typeof item !== 'string') continue;
    const s = item.split(/\s+/).join(' ').trim();
    if (s.length < 10) continue;
    const key = s.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(s);
    if (out.length >= 3) break;
  }
  return out;
}

function normalizeMessage(m) {
  if (!m || typeof m !== 'object') return m;
  if (m.role !== 'assistant') return { id: m.id, role: m.role, content: m.content };
  return { id: m.id, role: m.role, content: m.content, citations: normalizeCitations(m.citations), suggested_questions: normalizeSuggestions(m.suggested_questions) };
}

function deriveTitle(question) {
  const text = String(question || '').split(/\s+/).join(' ').trim();
  if (!text) return null;
  let title = text.slice(0, 60).trim();
  if (text.length > 60) title = title.rsplit(' ', 1)[0] || title;
  return title || null;
}

const isDefaultTitle = (t) => !t || String(t).trim() === '' || String(t).trim() === 'New conversation';

function sortConversations(list) {
  return [...list].sort((a, b) => {
    const da = new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0);
    return da;
  });
}

export const loadConversations = createAsyncThunk(
  'tutor/loadConversations',
  async ({ spaceId, projectId, page, pageSize }, { rejectWithValue }) => {
    try { return await listConversations(spaceId, projectId, { page: page || 1, page_size: pageSize || 20 }); }
    catch (e) { return rejectWithValue(describeApiError(e, 'load conversations')); }
  }
);

export const newConversation = createAsyncThunk(
  'tutor/newConversation',
  async ({ spaceId, projectId, title }, { rejectWithValue }) => {
    try { return await createConversation(spaceId, projectId, title); }
    catch (e) { return rejectWithValue(describeApiError(e, 'create a conversation')); }
  }
);

export const renameConversationThunk = createAsyncThunk(
  'tutor/renameConversation',
  async ({ spaceId, projectId, conversationId, title }, { rejectWithValue }) => {
    try { return await renameConversation(spaceId, projectId, conversationId, title); }
    catch (e) { return rejectWithValue(describeApiError(e, 'rename the conversation')); }
  }
);

export const removeConversation = createAsyncThunk(
  'tutor/removeConversation',
  async ({ spaceId, projectId, conversationId }, { rejectWithValue }) => {
    try {
      await deleteConversation(spaceId, projectId, conversationId);
      return { conversationId };
    } catch (e) { return rejectWithValue(describeApiError(e, 'delete the conversation')); }
  }
);

export const loadConversationMessages = createAsyncThunk(
  'tutor/loadConversationMessages',
  async ({ spaceId, projectId, conversationId }, { rejectWithValue }) => {
    try {
      const messages = await fetchConversationMessages(spaceId, projectId, conversationId);
      return { conversationId, messages };
    } catch (e) { return rejectWithValue(describeApiError(e, 'load messages')); }
  }
);

export const sendQuestion = createAsyncThunk(
  'tutor/sendQuestion',
  async ({ spaceId, projectId, conversationId, question, action }, { rejectWithValue }) => {
    try {
      const res = await askTutorInConversation(spaceId, projectId, conversationId, question, action);
      // Bind the response to the originating conversation, never to
      // whichever conversation happens to be active when it resolves.
      return { ...res, conversationId, question };
    } catch (e) { return rejectWithValue({ conversationId, message: describeApiError(e, 'ask the tutor') }); }
  }
);

const initialState = {
  conversations: [],
  conversationsMeta: { total: 0, page: 1, pageSize: 20, pages: 0 },
  projectKey: null,
  activeId: null,
  messagesById: {},
  loadedById: {},
  loadingById: {},
  sendingById: {},
  listStatus: 'idle',
  createStatus: 'idle',
  createError: null,
  error: null,
};

const slice = createSlice({
  name: 'tutor',
  initialState,
  reducers: {
    // Scoped optimistic user message — keyed by explicit id, never activeId.
    pushUser(state, a) {
      const { conversationId, content } = a.payload || {};
      if (!conversationId) return;
      if (!state.messagesById[conversationId]) state.messagesById[conversationId] = [];
      state.messagesById[conversationId].push({ role: 'user', content });
    },
    setActiveConversation(state, a) {
      state.activeId = a.payload || null;
    },
    // Called when space/project changes so no cross-project bleed is possible.
    resetForProject(state, a) {
      const key = a.payload || null;
      if (state.projectKey === key) return;
      state.conversations = [];
      state.conversationsMeta = { total: 0, page: 1, pageSize: 20, pages: 0 };
      state.projectKey = key;
      state.activeId = null;
      state.messagesById = {};
      state.loadedById = {};
      state.loadingById = {};
      state.sendingById = {};
      state.listStatus = 'idle';
      state.createStatus = 'idle';
      state.createError = null;
      state.error = null;
    },
    clearTutor(state) {
      state.conversations = [];
      state.conversationsMeta = { total: 0, page: 1, pageSize: 20, pages: 0 };
      state.activeId = null;
      state.messagesById = {};
      state.loadedById = {};
      state.loadingById = {};
      state.sendingById = {};
      state.listStatus = 'idle';
      state.createError = null;
      state.error = null;
    },
  },
  extraReducers: (b) => {
    b.addCase(loadConversations.pending, (s) => { s.listStatus = 'loading'; s.error = null; })
      .addCase(loadConversations.fulfilled, (s, a) => {
        s.listStatus = 'succeeded';
        s.conversations = sortConversations(pageItems(a.payload));
        s.conversationsMeta = pageMeta(a.payload);
      })
      .addCase(loadConversations.rejected, (s, a) => { s.listStatus = 'failed'; s.error = a.payload; })
      .addCase(newConversation.pending, (s) => { s.createStatus = 'creating'; s.createError = null; })
      .addCase(newConversation.fulfilled, (s, a) => {
        s.createStatus = 'idle';
        s.createError = null;
        s.conversations = sortConversations([...s.conversations, a.payload]);
        s.activeId = a.payload.id;
        s.messagesById[a.payload.id] = [];
        s.loadedById[a.payload.id] = true;
      })
      .addCase(newConversation.rejected, (s, a) => {
        s.createStatus = 'idle';
        s.createError = a.payload || 'Failed to create conversation';
        s.error = a.payload;
      })
      .addCase(renameConversationThunk.fulfilled, (s, a) => {
        s.conversations = s.conversations.map((c) => (c.id === a.payload.id ? a.payload : c));
      })
      .addCase(renameConversationThunk.rejected, (s, a) => { s.error = a.payload; })
      .addCase(removeConversation.fulfilled, (s, a) => {
        const { conversationId } = a.payload;
        s.conversations = s.conversations.filter((c) => c.id !== conversationId);
        delete s.messagesById[conversationId];
        delete s.loadedById[conversationId];
        delete s.loadingById[conversationId];
        delete s.sendingById[conversationId];
        if (s.activeId === conversationId) {
          s.activeId = s.conversations.length ? s.conversations[0].id : null;
        }
      })
      .addCase(removeConversation.rejected, (s, a) => { s.error = a.payload; })
      .addCase(loadConversationMessages.pending, (s, a) => {
        s.loadingById[a.meta.arg.conversationId] = true;
      })
      .addCase(loadConversationMessages.fulfilled, (s, a) => {
        const { conversationId, messages } = a.payload;
        s.loadingById[conversationId] = false;
        s.loadedById[conversationId] = true;
        s.messagesById[conversationId] = pageItems(messages).map(normalizeMessage);
      })
      .addCase(loadConversationMessages.rejected, (s, a) => {
        s.loadingById[a.meta.arg.conversationId] = false;
        s.error = a.payload;
      })
      .addCase(sendQuestion.pending, (s, a) => {
        s.sendingById[a.meta.arg.conversationId] = true;
      })
      .addCase(sendQuestion.fulfilled, (s, a) => {
        const { conversationId, answer, citations, flashcards, mcq, question, conversation_title, suggested_questions } = a.payload;
        s.sendingById[conversationId] = false;
        if (!s.messagesById[conversationId]) s.messagesById[conversationId] = [];
        s.messagesById[conversationId].push({
          role: 'assistant', content: answer, citations: normalizeCitations(citations),
          flashcards: Array.isArray(flashcards) ? flashcards : [],
          mcq: Array.isArray(mcq) ? mcq : [],
          suggested_questions: normalizeSuggestions(suggested_questions),
        });
        // Prefer the server-truth title (auto-generated from the first
        // question); fall back to the local mirror if the backend is older.
        s.conversations = sortConversations(s.conversations.map((c) => {
          if (c.id !== conversationId) return c;
          const next = { ...c, updated_at: new Date().toISOString() };
          if (isDefaultTitle(c.title)) {
            next.title = conversation_title || deriveTitle(question) || c.title;
          }
          return next;
        }));
      })
      .addCase(sendQuestion.rejected, (s, a) => {
        const cid = a.payload?.conversationId || a.meta.arg.conversationId;
        s.sendingById[cid] = false;
        s.error = a.payload?.message || 'Tutor request failed';
      });
  },
});

export const { pushUser, setActiveConversation, resetForProject, clearTutor } = slice.actions;
export default slice.reducer;
