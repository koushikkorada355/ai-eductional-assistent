import { configureStore } from '@reduxjs/toolkit';
import authReducer from '../features/auth/authSlice.js';
import spaceProjectReducer from '../features/project/spaceProjectSlice.js';
import tutorReducer from '../features/tutor/tutorSlice.js';
import quizReducer from '../features/quiz/quizSlice.js';

export const store = configureStore({
  reducer: {
    auth: authReducer,
    spaceProject: spaceProjectReducer,
    tutor: tutorReducer,
    quiz: quizReducer,
  },
});
