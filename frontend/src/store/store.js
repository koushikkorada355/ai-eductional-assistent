import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../features/auth/authSlice.js';
import spaceProjectReducer from '../features/project/spaceProjectSlice.js';
import tutorReducer from '../features/tutor/tutorSlice.js';
import quizReducer from '../features/quiz/quizSlice.js';
import assignmentsReducer from '../features/assignments/assignmentsSlice.js';
import conceptsReducer from '../features/concepts/conceptsSlice.js';
import analyticsReducer from '../features/analytics/analyticsSlice.js';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    spaceProject: spaceProjectReducer,
    tutor: tutorReducer,
    quiz: quizReducer,
    assignments: assignmentsReducer,
    concepts: conceptsReducer,
    analytics: analyticsReducer,
  },
});
