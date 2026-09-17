# Frontend — Complete Build Spec (for Figma Redesign)

> **Purpose:** Single source of truth for redesigning the `frontend/` template in Figma.
> Covers every route, layout, component, state, design token, interaction, and copy string built till now.
> App name: **AI Study Companion** — "your persistent, contextual learning partner."

---

## 1. Tech Stack & Project Structure

- **Framework:** React 18 + Vite 5 (`frontend/vite.config.js`, dev port `5173`)
- **Routing:** `react-router-dom` v6
- **State:** Redux Toolkit + `react-redux` (6 slices)
- **HTTP:** `axios` (`src/api/client.js`, baseURL `VITE_API_BASE_URL || http://localhost:8000/api/v1`, JWT `Bearer` from `localStorage.access_token`)
- **Animation:** `framer-motion` v11 (page entrances, tab pill, modals, lists, progress bars)
- **Fonts (Google Fonts, `index.html`):** `Inter` 400/500/600/700/800 (body), `Sora` 600/700/800 (headings)
- **No UI kit / no Tailwind** — all styling is hand-written CSS per component.

```
frontend/
  index.html
  vite.config.js
  src/
    main.jsx                    # Provider + BrowserRouter + App
    App.jsx / App.css           # Routes + Shell layout
    index.css                   # Design tokens + shared primitives
    api/client.js               # axios instance + auth interceptor
    store/store.js              # 6 reducers: auth, spaceProject, tutor, quiz, assignments, concepts
    components/
      Navbar/                   # Top bar + profile dropdown
      Sidebar/                  # Spaces → Projects tree + CRUD forms
      ConfirmModal/             # Reusable delete/submit dialog
      MasteryBars/              # (built, currently unused — simple mastery list)
      icons/Icons.jsx           # 18 custom stroke SVG icons
    features/
      auth/ (authApi, authSlice)
      project/ (projectApi, spaceProjectSlice)   # spaces, projects, documents
      tutor/ (tutorApi, tutorSlice)
      quiz/ (quizApi, quizSlice)
      assignments/ (assignmentsSlice)
      concepts/ (conceptsSlice)
    pages/
      Auth/                     # /login
      Dashboard/                # /
      ProjectWorkspace/         # /spaces/:spaceId/projects/:projectId
        Tabs/
          Materials/
          Concepts/
          AITutor/
          Quiz/
          Assignments/
          Analytics/
```

---

## 2. Routes & Navigation Map (redesign as 3 Figma pages + 6 tab states)

| Route | Guard | Layout | Content |
|---|---|---|---|
| `/login` | public, no shell | Full-screen centered | `Auth.jsx` — login / register toggle |
| `/` | `token ? Shell+Dashboard : → /login` | `Navbar` + `Sidebar` + `main` | `Dashboard.jsx` — hero + project card grid |
| `/spaces/:spaceId/projects/:projectId` | same guard | `Navbar` + `Sidebar` (active project highlighted) + `main` | `ProjectWorkspace.jsx` — 6 tabs |
| `*` | → `/` | — | redirect |

**Shell layout (`App.jsx`):**
- `.app-shell`: column flex, `min-height: 100vh`, background `radial-gradient(1200px 400px at 80% -100px, #e0e7ff) + var(--bg)`
- `.app-body`: row flex (`Sidebar` left, `main` right)
- `.main-content`: `flex:1`, `padding: 36px 40px`, `max-width: 1320px`, `min-width: 0`

---

## 3. Design System (recreate as Figma Styles + Variables)

### 3.1 Colors

| Token | Value | Usage |
|---|---|---|
| `--bg` | `#edf0f6` | app canvas |
| `--bg-soft` | `#f7f9fc` | inputs, bubbles, secondary surfaces |
| `--card` | `#ffffff` | cards, navbar, sidebar, modals |
| `--text` | `#243041` | body text |
| `--heading` | `#131c2e` | headings |
| `--muted` | `#66748c` | secondary text, placeholders |
| `--primary` | `#4338ca` | primary actions, links, active states |
| `--primary-dark` | `#3730a3` | gradient end, hover |
| `--primary-soft` | `#eeedfd` | selected / hover backgrounds |
| `--accent` | `#047857` | success-green accent, badges, avatar |
| `--accent-soft` | `#e3f5ee` | badge bg |
| `--border` | `#dfe5ee` | borders (also `#e5e7eb` / `#d1d5db` inside Assignments+Concepts tabs — normalize in redesign) |
| `--success / --success-soft` | `#15803d` / `#dcfce7` | quiz good, doc `ready` |
| `--warning / --warning-soft` | `#b45309` / `#fef3c7` | quiz active tracker, doc `queued` |
| `--danger / --danger-soft` | `#b91c1c` / `#fee2e2` | errors, delete |
| Auth hero gradient | `linear-gradient(135deg, #131c2e 0%, #2b3590 60%, #047857 140%)` | login page bg |
| Primary button gradient | `linear-gradient(135deg, #4338ca, #3730a3)` | `.primary`, chat send, tab pill, user bubble |
| Progress fill (dashboard) | `linear-gradient(90deg, var(--primary), var(--accent))` | project % bar |
| Avatar gradient | `linear-gradient(135deg, #047857, #34d399)` | navbar avatar |
| Brand mark gradient | `linear-gradient(135deg, #4338ca, #6d64f0)` | logo tile |

### 3.2 Typography

- Body: `Inter`, `18px` base (`html { font-size: 18px }`), `1rem`, `line-height 1.7`, `letter-spacing 0.005em`
- Headings: `Sora`, `color: heading`, `line-height 1.28`, `letter-spacing -0.015em`
  - `h1 2.6rem/800`, `h2 2.1rem/800`, `h3 1.55rem/700`, `h4 1.2rem/700`
- Small/legend: `0.85–0.92rem`; badges: `0.78–0.82rem/700 uppercase` (dashboard space pill, chat sources title)

### 3.3 Shape, Shadow, Spacing

- Radii: `--radius-sm 8px`, `--radius-md 10px`, `--radius-lg 12px`; pills `999px`; chat `12px` (inner corner `4px`); score ring `50%`
- Shadows: `sm 0 1px 3px rgba(19,28,46,.08)`, `md 0 8px 24px -8px rgba(19,28,46,.16)`, `lg 0 20px 48px -16px rgba(19,28,46,.24)`
- Content gaps: page sections `20–26px`; cards padding `24–46px`; main `36px 40px`; navbar height `76px`; sidebar width `300px`

### 3.4 Shared Primitives (`index.css` — make Figma components)

- **`.primary`**: gradient bg, white, `13px 22px`, `1.02rem/600`, `radius-md`, hover `brightness(1.07)+md shadow`, disabled `55%`
- **`.secondary`**: white, `1px border`, `11px 18px`, `1rem/600`; hover `primary border + primary-soft bg`
- **`.link-btn`**: text-only primary, `600`, underline on hover
- **`.card` / `.placeholder-card`**: white, border, `radius-md/lg`, `md` shadow; placeholder `30px` padding
- **Inputs/textarea/select**: `1.02rem`, focus `2px primary outline`; auth inputs `14px 16px`, `1.5px border`, `bg-soft → white on focus`
- **`.spinner`**: `26px` ring, `border-top primary`, `0.8s spin`
- **`.error`**: danger, `0.95rem/500`; `.muted`: muted color; `.small`: `0.85rem`
- **Status pills** (`Materials` + `Assignments` variants — unify in Figma):
  - Docs: `queued` amber, `processing` blue `#dbeafe/#1d4ed8`, `ready` green, `failed` red; `0.82rem/700`, `6px 14px`, `999px`, capitalized
  - Assignments: `ready` green, `submitted` blue, `draft` gray, `generating` amber, `evaluating` indigo, `failed` red

### 3.5 Icons (`components/icons/Icons.jsx` — 24px stroke set, `strokeWidth 1.8`, round caps)

`IconFolder, IconChat, IconTarget, IconChart, IconChevron, IconPencil, IconTrash, IconPlus, IconX, IconCheck, IconArrowRight, IconArrowLeft, IconUpload (40px), IconFile, IconBook (26px), IconSpark, IconClipboard (40px), IconGraduation (26px)`. Default sizes: nav/tab `18–20px`, auth hero `26px`, empty states `40–48px`.

### 3.6 Motion (Framer Motion — note as Figma Smart-Animate specs)

- Page/tab enter: `opacity 0→1, y 10–18px, 0.2–0.35s`; lists stagger `0.02–0.05s` per item
- Active tab pill: `layoutId="tab-pill"`, spring `stiffness 420, damping 34`
- Buttons: `whileHover scale 1.015–1.03 / y -5`, `whileTap 0.96–0.99`
- Modal/dropdown: scale `0.94–0.98 + y ±12px`, `0.15s`
- Progress/mastery bars: width animate `0.6s`

---

## 4. Global Components (design each as Figma component with variants)

### 4.1 Navbar (`Navbar.jsx/css`) — sticky top bar

- Container: `76px` tall, white, bottom border, `0 36px` padding, `sticky top 0, z 20`
- Left: brand (click → `/`): `44px` rounded-10 gradient tile with letter **"A"** (`Sora 800, 1.35rem`) + text **"AI Study *Companion*"** (`Sora 800, 1.35rem`; "Companion" in primary)
- Right: **Profile pill** (`999px`, border, `7px 17px 7px 7px`): `36px` green-gradient avatar **"U"** + label "Profile" → dropdown (`200px` white card, `8px` pad, `lg` shadow) with single item **Logout** (hover: danger-soft bg, danger text). Logout clears token → `/login`.

### 4.2 Sidebar (`Sidebar.jsx/css`) — `300px`, white, right border, `28px 18px` pad, scrollable

- Header: uppercase micro-label **"MY LEARNING SPACES"** (`0.82rem/700, muted, 0.12em`) + **"+ New"** mini-btn (bg-soft, primary text, `7px 12px`, `0.88rem/700`)
- **New space form** (expandable): 1 input "Space name" + Add button
- **Space block**: row with chevron (rotates 90° when open) + bold name (`1.05rem/700`); hover reveals ✎ / 🗑 icon buttons (`opacity 0 → 1` on hover)
  - Rename → inline input + Save + ✕; Delete → `ConfirmModal` ("Delete space?" / `"X" and all its projects will be permanently removed.`)
  - Expanded: indented (`26px`) project list
- **Project row**: file icon + name; hover `primary-soft`; active: `primary-soft + bold + 3px primary left border`; hover-reveal rename/delete; delete modal ("Delete project?" / `"X" and its materials will be permanently removed.")
- **New project form** (stacked): "Project name" + "Learning goal" inputs + Add / ✕. Payload note: `description = name`, `learning_goal` required.
- **"+ Project"** mini-btn under each space; empty texts: "No spaces yet…", "No projects yet" (`0.95rem muted`)
- Click project → navigate to workspace route.

### 4.3 ConfirmModal (`ConfirmModal.jsx/css`) — reusable dialog

- Backdrop: fixed, `rgba(19,28,46,.45) + 3px blur`, centered, click-outside cancels
- Card: `440px`, white, `radius-lg`, `lg` shadow, `32px` pad: `h3` title + muted message + right-aligned actions [Cancel `secondary`] [Delete/Submits `danger-btn` solid danger `11px 20px`]
- Used for: delete space, delete project, quiz submit (`confirmLabel="Submit"`, message counts unanswered).

### 4.4 MasteryBars (`MasteryBars.jsx` — built but unused)

- Empty: "No concepts yet. Upload PDFs to generate mastery tracking."
- Rows: `name … %` label + gray track + animated fill. (Concepts tab uses a richer card version instead — see §6.2.)

---

## 5. Pages

### 5.1 Auth — `/login` (`Auth.jsx/css`)

Full-viewport (`100vh`), centered, `70px` gap, `44px` pad, dark gradient bg. Two-panel:

1. **Hero (desktop only, ≥960px, `max 500px`, white text):**
   - H1: "Meet your persistent study partner."
   - Sub (`1.2rem, #c9d4ef`): "Upload your materials, chat with a grounded AI tutor, take adaptive quizzes, and watch your mastery grow."
   - 3 glass cards (`rgba(255,255,255,.1)`, white/16 border, `16px 18px`): [book icon] "Chat grounded strictly in your PDFs, with citations" · [target] "Adaptive quizzes that target your weak concepts" · [graduation] "Mastery tracking that remembers what you struggle with" (staggered entrance `0.2/0.32/0.44s`)
2. **Card (`450px`, white, `46px 44px`, `radius-lg`, `lg` shadow, entrance `y 20 + scale .98`):**
   - H2: "Welcome back" / "Create account"; sub: "Pick up right where you left off." / "Start your learning journey today."
   - Labels Email + Password; inputs `you@example.com` / `••••••••` (password type)
   - Error banner (danger-soft, `11px 15px`, `8px` radius) on failure
   - Submit: gradient, `15px`, `1.08rem/700` — "Login" / "Register" / "Please wait…"
   - Toggle link: "Need an account? Register" ↔ "Have an account? Login"
- Behavior: login success → `/`; register success → back to login mode.

### 5.2 Dashboard — `/` (`Dashboard.jsx/css`)

Column, `26px` gap.

- **Hero card** (white, border, `radius-lg`, `34px 38px`, flex space-between): H2 "Learning Dashboard" + muted line — empty: "Create a space and project from the sidebar to begin." / filled: "You're working across N space(s) and M project(s)." Right (if projects exist): **"Continue Learning →"** primary → first project.
- **Card grid**: `repeat(auto-fill, minmax(300px, 1fr))`, `20px` gap. Each card (`28px` pad, hover `y -5` + deep shadow, click → workspace): emerald uppercase pill (space name) + `h4` project name (`1.3rem`) + muted description ("No description" fallback) + gradient progress bar (`10px` track `#e8edf5`) + "N% complete" (`0.9rem/600 muted`).
- **Empty state** (`placeholder-card`): H3 "No projects yet" + 'Use the **+ New** button in the sidebar to create a Space, then add a Project inside it.'

### 5.3 Project Workspace — `/spaces/:spaceId/projects/:projectId` (`ProjectWorkspace.jsx/css`)

- **Tab bar** (white pill container: `7px` pad, border, `12px` radius, `md` shadow, fit-content): 6 buttons `12px 22px, 1.02rem/600, muted` with `19px` icons — Materials 📁 · Concepts 📖 · AI Tutor 💬 · Quiz 🎯 · Assignments 📄 · Analytics 📊. Active: white text over animated gradient pill.
- Content cross-fades (`y ±10px, 0.2s`) per tab.

---

## 6. Workspace Tabs (each = 1+ Figma frames with empty/loading/content/result states)

### 6.1 Materials (`Materials.jsx/css`)

- **Dropzone** (white, `2px dashed #b9c4d8`, `radius-lg`, `52px 30px`, centered, `md` shadow): upload icon (primary, 40px) + bold `1.3rem` "Drag & drop your PDF here" / "Uploading…" + muted "or click to browse files". States: hover/drag → primary border (+ `primary-soft` bg + `scale 1.015`). Hidden `<input accept="application/pdf">`.
- Uploading line: spinner + "Uploading PDF…"; error line (danger) e.g. "PDF upload failed. Please try again."
- Hint (muted `1rem`): "Uploaded PDFs are processed asynchronously in the background. Text is extracted, chunked, and converted into vector embeddings for the AI Tutor."
- **H4 "Documents (N)"** + rows (white, border, `radius-md`, `17px 20px`, `md` shadow): file icon (primary) + filename (ellipsis) + status pill (`queued/processing/ready/failed`). Empty: "No documents yet. Upload your first PDF above."

### 6.2 Concepts (`Concepts.jsx/css`) — ⚠️ uses its own gray palette (`#f3f4f6/#e5e7eb/#1f2937` + `13px` type) — normalize to design tokens in redesign

- Header: H2 "Project Concepts" + muted "Extracted from your materials. Mastery updates automatically when you submit quizzes and assignments." + gray "Refresh" / "Refreshing…" button (`10px 18px`, `13px/600`, `8px` radius).
- Red error banner; loading "Loading concepts…"; empty dashed box: "No concepts yet. Upload a PDF in Materials to generate concepts for this project."
- **3 stat cards** (white, `14px 16px`, `10px` radius): count "Concepts" · "Avg mastery %" · "Weakest concept" name.
- **Grid** (`minmax(300px,1fr)`, `14px` gap): concept cards (`16px` pad): top row `h3 14px/600` name + level badge (`11px/700`, `3px 10px`, pill): **Strong ≥70** green `#dcfce7/#15803d` · **Learning 40–69** blue `#dbeafe/#1d4ed8` · **Needs work <40** red `#fee2e2/#b91c1c`; optional 3-line-clamped description (`13px muted`); "Mastery … N%" label (`12px/600`); `8px` track with matching fill (green `#16a34a` / indigo `#6366f1` / red `#dc2626`), animated. Sorted weakest-first.

### 6.3 AI Tutor (`AITutor.jsx/css`)

- Panel: white, border, `radius-lg`, `md` shadow, `28px` pad, `min-height 520px`, column.
- **Chat list** (`340–540px`, scroll, `14px` gap): empty state (centered, `56px 24px`): 44px chat icon + H4 `1.4rem` "Ask anything about your materials" + muted "Answers come strictly from your uploaded documents, with page citations." (`max 460px`).
- **Bubbles** (`max 78%`, `15px 19px`, `12px` radius, `1.02rem/1.7`): user right-aligned gradient white text (inner corner `4px`); assistant left gray w/ border. Thinking indicator: 3 bouncing primary dots. Inline citations rendered as chips (`primary-soft` bg, `#c7d2fe` border, `3px 10px`, `0.85rem/700`, nowrap, e.g. `[Source: Page 3]`).
- **With sources** → 2-column `qa-row` (`12px` gap; stacks on ≤900px): assistant bubble (flex-1) + **Sources panel** (`270px`, bg-soft, border, `10px` radius, `12px` pad, scroll `max 320px`): uppercase micro title "SOURCES" + white source cards (`9px 12px`): bold doc name + green page pill (`accent-soft`, `2px 10px`, `0.78rem`) + muted excerpt (`0.9rem`).
- **Input row** (`12px` gap): growing input (`15px 20px`, `1.03rem`, `10px` radius, bg-soft) "Ask about this project's materials…" + gradient Send button (`15px 28px`, arrow icon).

### 6.4 Quiz (`Quiz.jsx/css`) — 4 views, most complex flow

State machine: `start → generating → answering → evaluating → results`, plus resume/view of past attempts. Polls every `4s` during generating/evaluating.

1. **`start`**: 2-col (stacked): setup card (`max 680px`, `34px` pad): clipboard icon + H3 "Start a new quiz" + muted "Name your quiz and describe what to test. Questions are generated from your uploaded materials." Form: "Quiz name *" (`Photosynthesis Basics`, `max 100`, error "Quiz name is required."), "Learning goal (optional — leave blank to test weakest concepts)" textarea (`max 500`, `3` rows), **MCQ stepper** + **Open-ended stepper** rows (`−`/`+` `38px` buttons + numeric `64px` input, `0–10` each, total must be `1–10`, error "Pick 1–10 questions in total…"; helper "Order: all N MCQs first, then M open-ended — T total."). Submit primary "Generate quiz · N questions →" / "Creating…". Below/after: "Previous attempts" card — rows (bg-soft, border, `15px 18px`): name (ellipsis) + score/status right (`completed→"N%"` green≥60 else red; `in_progress→Resume`, `generating→Generating…`, `evaluating→Grading…`; `failed` disabled). Errors + "Loading quiz…".
2. **`generating` / `evaluating`**: centered card (`60px 32px`) — spinner + 'Building "NAME"' / "Reading your materials and crafting questions…" / "Grading your quiz" / "Evaluating answers and updating your mastery…".
3. **`answering`** (`.quiz-layout`: `2fr 1fr` grid → 1 col ≤900px): question card (`34px`): meta micro-caps "Question i of N · type" + thin (`8px`) progress + H3 `1.6rem` question; MCQ = 2-col grid (1-col ≤700px) option buttons (`16px 18px`, `1.5px` border, hover primary; selected `primary-soft + primary border`); open = textarea (`5` rows, "Write your answer…"). Actions row: [← Previous] [Save answer/Saving…/✓ Saved (green-bordered)] [Next →]. Saved note (green ✓ "Answer saved…"). Full-width "Submit Quiz" primary (`16px`, `1.1rem`) → ConfirmModal ("Submit quiz?" / "N question(s) still unanswered…" or "Submit for evaluation?…"). Right **tracker** (sticky `top 100px`, `24px` pad): quiz name + numbered `44px` circles (`saved` green ring, `active` amber ring+shadow, `todo` gray) + legend (Saved/Active/Unattempted dots).
4. **`results`**: header (H3 name + "N questions answered" + `96px` score ring `6px` border, green/red) + "← Back to quizzes" link + per-question cards (left `5px` green/red border): "Qi. text" + "Your answer:" + (MCQ) "Correct answer:" + "Score N" (`800`) + muted feedback + "Review: concepts…" small.

### 6.5 Assignments (`Assignments.jsx/css`) — 5 sub-views, MCQ-only (also own gray palette — normalize)

Flow: `list → create → select-concepts → generating → view (ready/grading/submitted)`. Polls `4s` while generating/evaluating.

- **`list`**: H2 "Your Assignments" + indigo `#6366f1` "+ New Assignment" btn (`12px 20px`, `14px/600`, `8px` radius; hover `#4f46e5`). Grid (`minmax(320px,1fr)`, `16px`): cards (white, `16px` pad, hover indigo border+glow, click opens): header (H3 `14px/600` title + status pill `11px`) + meta row ("N MCQ(s)" + score badge `perfect/pass/fail` when submitted) + footer date. Empty dashed: "No assignments yet. Create one to test your understanding!"
- **`create`** (white, `24px`, `12px` radius, `max 800px` centered): H2 "Create New Assignment" + "Generates multiple MCQ questions from your concepts, grounded in your materials." Step 1 "Select Concepts" → full-width select button ("Select concepts…" / "N concept(s) selected"); Step 2 "Title (Optional)" input ("Photosynthesis Practice Set", `max 200`); Step 3 "Number of Questions" preset chips `[3,5,8,10]` (active indigo). Actions right: Back (gray) + "Generate N MCQs" / "Generating MCQs…" (disabled if no concepts/loading).
- **`select-concepts`**: H2 "Select Concepts" + "Click to select/deselect…": scrollable (`max 400px`) checkbox list rows: name + optional desc + mini mastery bar (`max 220px`, `6px`, green/indigo/red by same 70/40 rule) + "N% mastery". Empty: "No concepts found. Upload a PDF…" Actions: Cancel / Done.
- **`view`**: header [← Back to Assignments] + status pill; H2 title; **submitted** score banner (`perfect` green / `pass` blue / `fail` red, `16px` pad): "Score: S/T" (`18px`) + overall feedback; **evaluating** indigo grading banner (spinner + "Grading your answers… results appear automatically."); **ready** progress line "Answered A/T" + `8px` indigo progress; question cards (bg `#f9fafb`, `16px` pad, green/red tint when submitted): "Qi. text" + option buttons (radio dot; `picked` indigo, `answer` green, `wrong-pick` red; right tags "Correct"/"Your pick"; disabled after submit). Submit button (`12px 24px` indigo): "Submit Assignment (A/T)". `failed` → red banner "Question generation failed…".
- **`generating`**: centered card: 'Building "TITLE"' + "Reading your materials and crafting MCQs…" + spinner + Back; failure variant: "Generation failed" + "The graph could not generate questions…".

### 6.6 Analytics (`Analytics.jsx/css`) — placeholder only

Centered `placeholder-card` (`64px 32px`): 48px chart icon (primary) + H3 `1.6rem` "Learning Analytics" + muted (`max 560px`): "Concept mastery, progress trends, and recommendations will appear here once quiz activity is available. Complete a quiz to unlock your insights." → **Design freely in Figma** (trend charts, mastery overview, recommendations).

---

## 7. State & Data Notes (for prototype copy / empty states)

- **Redux slices:** `auth {token,status,error}` · `spaceProject {spaces, projectsBySpace, documents, status, error}` · `tutor {messages[{role,content,citations[]}],status}` · `quiz {view,quizId,name,questions[],index,drafts,attempts,average,status,error}` · `assignments {assignments,selectedAssignment, status,error}` · `concepts {concepts[{id,name,description,mastery_level}],status,error}`. Citation: `{pdf_name, page_number, chunk_excerpt}`.
- **Question types:** `multiple_choice` (options[], correct_answer) vs open-ended (textarea). Assignment questions are MCQ-only.
- **Mastery rule (global):** `≥70 Strong/green`, `40–69 Learning/blue-indigo`, `<40 Needs work/red`.
- **Quiz/assignment backends are async:** creation → `generating` (poll 4s) → `ready`; submit → `evaluating` → `submitted/completed` with scores + feedback + `missing_concepts`.
- **Auth:** JWT persisted in `localStorage`; all API calls attach `Authorization: Bearer`.

---

## 8. Responsive Rules to Preserve

- Auth hero hidden `<960px` (card only, full width).
- Dashboard grid auto-fills `≥300px` cards; hero stacks on narrow.
- Workspace tabs wrap (`max 100%`); AI Tutor sources stack under bubble `≤900px`; Quiz layout `2fr+1fr → 1fr ≤900px`, MCQ grid `2→1 col ≤700px`.
- Sidebar `300px` fixed; main scrolls; tracker `sticky top 100px` (unstick on mobile).

---

## 9. Figma Redesign Checklist

**Pages/frames to draw:** (1) Login + Register states (+error/loading) · (2) Dashboard empty + filled (+hover) · (3) Workspace with 6 tab frames · (4) Materials (default/uploading/error/with docs) · (5) Concepts (stats + grid + empty) · (6) AI Tutor (empty/chat/thinking/with-sources/mobile) · (7) Quiz setup/attempts/generating/answering+tracker/evaluating/results · (8) Assignments list/create/select-concepts/generating/take/grading/submitted · (9) Analytics (new design) · (10) Modals: delete-space, delete-project, submit-quiz · (11) Sidebar states: empty, space form, project form, rename, active project.

**Figma components + variants:** Button (primary/secondary/danger/ghost × default/hover/disabled/loading) · Input/textarea/stepper · Card · Status pill (queued/processing/ready/failed + draft/generating/evaluating/submitted × counts) · Avatar/profile menu · Space row / Project row · Tab bar + active pill · Chat bubbles (user/assistant/thinking/citation/source-card) · Concept card (strong/learning/weak) · Quiz option (default/selected) + tracker dot (saved/active/todo) + score ring (good/bad) · Assignment card + MCQ option (picked/answer/wrong) + score banner (perfect/pass/fail) · Modal · Spinner · Empty-state · Progress bars.

**Suggested improvements while redesigning (current inconsistencies):** unify the two gray palettes (`#e5e7eb` vs `--border`) into one token set; give Analytics a real dashboard; add failed/retry + offline states; add keyboard focus rings, tooltips for icon-only buttons, and mobile nav (sidebar → drawer).
