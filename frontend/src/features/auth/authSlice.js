import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { loginUser, registerUser } from './authApi.js';

export const login = createAsyncThunk('auth/login', async (payload, { rejectWithValue }) => {
  try {
    return await loginUser(payload);
  } catch (e) {
    return rejectWithValue(e.response?.data?.detail || 'Login failed');
  }
});

export const register = createAsyncThunk('auth/register', async (payload, { rejectWithValue }) => {
  try {
    return await registerUser(payload);
  } catch (e) {
    return rejectWithValue(e.response?.data?.detail || 'Registration failed');
  }
});

const slice = createSlice({
  name: 'auth',
  initialState: {
    token: localStorage.getItem('access_token') || null,
    status: 'idle',
    error: null,
  },
  reducers: {
    logout(state) {
      state.token = null;
      localStorage.removeItem('access_token');
    },
  },
  extraReducers: (b) => {
    b.addCase(login.pending, (s) => { s.status = 'loading'; s.error = null; })
      .addCase(login.fulfilled, (s, a) => {
        s.status = 'succeeded';
        s.token = a.payload.access_token;
        localStorage.setItem('access_token', a.payload.access_token);
      })
      .addCase(login.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload; })
      .addCase(register.pending, (s) => { s.status = 'loading'; s.error = null; })
      .addCase(register.fulfilled, (s) => { s.status = 'succeeded'; })
      .addCase(register.rejected, (s, a) => { s.status = 'failed'; s.error = a.payload; });
  },
});

export const { logout } = slice.actions;
export default slice.reducer;
