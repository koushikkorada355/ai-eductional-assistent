# AI Study Companion

An app for learning from your own books. Upload books, ask the tutor, take quizzes, and see how you improve over time.

Learning flow is simple. Make a space, make a project, upload a book, ask the tutor, take a quiz, check mastery, and keep learning.

## Features

Login and register with safe password storage and token based access.

Spaces to group work and projects to group one subject with strict ownership.

Book upload with background processing. Books are read page by page and made ready for search.

AI tutor that answers only from your uploaded books with page reference and follow up questions.

Quick actions for summary, deep study, flashcards, and practice questions.

Concepts that show what you learned and how strong you are in each topic.

Quizzes with choice questions and written questions. Quiz results update your mastery and history.

Assignments for practice with instant score and feedback.

Analytics for global progress and per project mastery, growth, and next steps.

Admin view to see users, spaces, projects, activity, AI use, evaluation, jobs, and system health.

Activity feed that records learning steps in simple words.

## Stack

Frontend with React and Vite.

State with Redux Toolkit.

Motion for smooth screens.

Backend with FastAPI and Python.

Input checks with Pydantic.

Login with JWT and bcrypt.

AI flow with LangGraph for tutor and quiz steps.

Search with pgvector inside Postgres.

Background jobs with Celery and Redis.

Database with Postgres and pgvector.

Logs in plain text for easy debug.

## Models used

Chat with Inception Mercury. Model is mercury 2.5. Used for tutor answers, quiz questions, assignments, and follow up ideas.

Backup chat with Groq. Used only when main chat key is not set.

Search vectors with Google Gemini embeddings. Used to find the right part of the book for tutor, quiz, and concepts.

Tracing with LangSmith when keys are set. Used to check what the AI did.

Text reading for scanned books with Tesseract OCR as fallback.

## What you need before start

You need Docker and Docker Compose for easy run.

You need a Postgres database url. Local default from compose also works.

You need a Redis url. Local default from compose also works.

You need a chat key for Inception Mercury for tutor and quiz.

You need an embedding key for Google Gemini for search. Without this, book search will not work.

Optional Groq key as backup chat. Optional LangSmith keys for tracing.

## How to run

Copy the example env file to env and fill the keys. Never commit the real env file.

Build and start all services with docker compose up with build in detached mode.

Open the frontend in browser on port 5173.

Check backend health on port 8000 with health path. It should say healthy.

Check queue health on health queue path to see Redis and worker status.

Stop all services with docker compose down when done.

## Admin login

The admin account is created on startup if it does not exist.

Email is admin@gmail.com and password is 12345.

You can change it with admin email, admin password, and admin name in env. If you change it, restart the app.

Only admin role can open the admin page. Normal users are sent back to home.

## How to use as a student

Register a new account and login.

Make a space like exam name or semester. Make a project like subject name inside it.

Open the project and go to materials. Upload a PDF book and wait till status becomes ready. If it fails, read the reason and press retry.

Open concepts to see key topics found from your book and your current level.

Open AI tutor to ask questions. Ask clearly from book topics. You will get an answer with page reference. Click follow up chips to learn more.

Use quick actions when you want a fast summary or practice set.

Open quiz to start a test. Choose count and type. Answer all questions and submit. Check score, feedback, and review.

Open assignments for extra practice. Submit once and see instant result.

Open analytics to see mastery bars, growth, quiz trend, and what to study next.

Use the home page to continue recent work and the global analytics page to see full progress.

## How to use as an admin

Login with the admin account and open the admin page.

See total users, projects, books, quizzes, and system health at the top.

Open users to search, list, and see one user journey with spaces, scores, and events.

Open spaces and projects to see all work across users with owner info.

Open activity to see learning events with filters by type and user.

Open AI usage to see calls, tokens, cost, and time per feature and model per day.

Open evaluation to see tutor quality, search grounding, and quiz results in simple form.

Open jobs to see worker status and recent failures.

Open health to see database, Redis, AI keys, and storage status.

## Demo data

You can seed demo evaluation data for testing dashboards and charts.

Run the seed script inside the backend container. Use force flag to reseed if needed.

This helps to see admin charts without manual uploads.

## Keys you need in detail

You need a database url for Postgres. This is required.

You need a secret key for login tokens. This is required. You can also use JWT secret key name.

You need a chat key for Inception Mercury. The model is mercury 2.5. This is required for tutor and quiz.

You need an embedding key for Google Gemini. It is needed for search. Without this, uploads will fail.

You need a Redis url for background jobs. This is required. Web and worker must use the same value.

You need frontend url for production to allow safe access. Local use works without it.

You can set upload folder path and max upload size in MB. Default is fine for local use.

Groq key is optional as backup. LangSmith keys are optional for tracing. OCR key is optional. Tesseract is used as fallback.

## Ports and services

Frontend runs on port 5173.

Backend runs on port 8000.

Postgres runs on port 5433 in local compose.

Redis runs on port 6379 in local compose.

## Health and debug

If uploads stay in queued for long, check queue health first.

It tells if Redis is down, if the URL is wrong, or if no worker is running.

Web and worker must share the same Redis url and the same upload storage. After changing env, restart the service and redeploy.

If a book fails, the reason is shown in materials. Common reasons are scanned images with no text, too many pages, quota over, or missing keys. Full details stay in server logs.

If the tutor says no proof, upload more books on that topic or ask in a narrower way.

## Safety and privacy

Each user can see only their own spaces and projects.

Search is strictly filtered by project. No cross project data is shared.

Raw provider errors are not sent to users. Users see only short safe messages.

Real env file is ignored by git. Never share keys in chat or screenshots.
