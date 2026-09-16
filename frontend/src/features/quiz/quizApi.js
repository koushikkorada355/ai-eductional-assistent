import api from '../../api/client.js';

export const createQuiz = (projectId, payload) =>
  api.post(`/projects/${projectId}/quiz/start`, payload).then((r) => r.data);
export const saveAnswer = (quizId, questionId, answer) =>
  api.patch(`/quiz/${quizId}/questions/${questionId}/save`, { answer }).then((r) => r.data);
export const submitQuiz = (quizId) =>
  api.post(`/quiz/${quizId}/submit`).then((r) => r.data);
export const fetchMastery = (spaceId, projectId) =>
  api.get(`/spaces/${spaceId}/projects/${projectId}/mastery`).then((r) => r.data);
export const fetchAttempts = (projectId) =>
  api.get(`/projects/${projectId}/quizzes`).then((r) => r.data);
export const fetchQuizDetail = (quizId) =>
  api.get(`/quiz/${quizId}`).then((r) => r.data);
