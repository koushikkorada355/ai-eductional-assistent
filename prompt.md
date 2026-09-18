# prompt.md — Development Prompts Log (300)

> AI usage (assistant, LLM/embedding models): see `AI_USAGE.md`.

## Prompts

1. build register and login with jwt tokens
2. hash passwords with bcrypt pls
3. mail was not validited properly
4. duplicate email should give 409 not 500
5. add password length validation
6. need a /me endpoint for current user
7. protect all routes with login required
8. set token expiry and proper 401 message
9. seed default admin account on startup
10. add role field user and admin
11. login error should not tell which one is wrong
12. let user update their display name
13. add change password endpoint
14. make proper Token and UserOut schemas
15. show wrong password message clearly in frontend
16. logout should clear everything
17. validate email format on register form also
18. admin guard for admin routes only
19. return user id in login response too
20. handle expired token in frontend silently refresh or logout
21. Database Schemas for Spaces and Projects, exact columns as I give
22. spaces crud now
23. projects crud nested under spaces/{space_id}/projects
24. user should see only own spaces strictly
25. cascade delete space with all projects inside
26. validate space name 1-100 chars
27. duplicate space name give 409
28. compute overall_progress from mastery scores
29. learning_goal required for tutor grounding
30. space list should include project counts
31. paginate all list apis
32. search spaces by name
33. search projects by name also
34. rename space and project option
35. delete project should remove docs also
36. project detail with stats counts
37. order everything newest first
38. accessing others space should look like 404
39. same name project in different space is okay right, allow it
40. description max 500 chars validation
41. show project counts in sidebar
42. confirm modal before deleting space
43. after delete redirect to dashboard
44. empty spaces show nice empty state
45. recent spaces on top of dashboard
46. build document ingestion pipeline pdf to vectors
47. Document and DocumentChunk models with project_id fk
48. materials should belong to project not space strictly
49. use Vector(768) for gemini embedding not 3072
50. chunked upload writing 1MB loop dont block event loop
51. worker says Document not found, resolve this and verify code once
52. for materials endpoint why need space_id in url
53. duplicate file upload should say already uploaded 409
54. same filename in same project give 409
55. password protected pdf tell user to remove password
56. cap 300 pages max per upload with split message
57. cap 2000 chunks max
58. reject empty files at upload itself
59. check %PDF header for valid pdf
60. scanned pdf with no text try OCR fallback
61. retry should clear old chunks and reset error
62. retry button should be safe to press many times
63. delete doc must remove chunks and file also
64. show pages and chunks count in list
65. evidence endpoint with page numbers excerpts
66. status flow queued processing ready failed properly
67. after doc ready auto extract concepts
68. file too big give 413 with actual size
69. corrupt pdf say re-export and upload again
70. no text pdf give actionable message
71. never send server file path to frontend
72. paginate documents list
73. doc detail with status error pages chunks
74. temp file cleanup on duplicate
75. only pdf allowed message
76. drag and drop upload in materials tab
77. upload progress bar while uploading
78. show queued badge few seconds normal
79. processing badge with spinner
80. ready badge green with counts
81. failed badge red with reason below
82. toast on upload success
83. toast on upload fail with reason
84. dont allow re-upload same content, point to existing doc
85. view button opens evidence viewer
86. wire gemini embedding model for docs
87. embed in small batches of 32
88. create vector extension on startup
89. vector search must filter by project_id always
90. retrieve top 5 chunks only
91. add similarity score threshold
92. store page number in every chunk metadata
93. add vector index for speed
94. fix dimension mismatch migration 1536 to 768
95. can you test some chunks test by you own query
96. splitter 1000 chunk 150 overlap
97. empty question should not call embedding
98. no chunks means tell user to upload first
99. query embedding same model as docs
100. log retrieval count per question for usage view
101. Update tutor_graph.py with RAG retrieve grade generate
102. quiz was not generated and tutor says cannot answer for everything, check entire codebase first and fix
103. add intent router, general chat bypass RAG, RAG for materials questions
104. grade_documents node yes no relevance check
105. answers must cite [Source: Page X]
106. general questions like hii should not hit retrieval
107. in aitutor after ai response give recommendations questions styled properly
108. dont recommend for general questions only RAG ones
109. recommended question on click must be answerable fix it
110. questions recommend but it not good questions fix it
111. strictly only recommend through conversations and concepts only
112. dont say i cannot provide based on material use creative words instead
113. no recommendations while answering, only after answer
114. remove the date below conversation
115. store chat sessions per project
116. keep last N turns only for context
117. strict system prompt answer only from materials
118. insufficient evidence reply should guide user what to do next
119. follow up questions should use history context
120. define chat request response schemas
121. organize ai files nodes state graph folders and verify imports
122. can you verify the import i think there wrong in ai
123. these node names not exist in nodes right confirm
124. explain this __init__.py file
125. cap context tokens per answer for cost
126. zero docs means tell user upload first
127. keep answers short and readable
128. show typing indicator while ai responds
129. suggestion chips clickable style
130. citations clickable to evidence page
131. clear chat button per session
132. conversation list in tutor sidebar
133. delete conversation option
134. rename conversation auto from first question
135. copy answer button
136. regenerate answer button
137. dislike button for bad answers for eval
138. show model name in admin usage not in chat
139. handle ai quota error with wait and retry message
140. timeout message with retry in moment
141. extract concepts task after doc ready
142. Concept model name mastery score project
143. silent mastery eval after chat answers
144. quiz submit should update mastery
145. now render concepts in frontend and mastery score also for it
146. define 0-100 mastery formula clearly
147. new concepts start at neutral 50
148. no duplicate concepts per project merge them
149. concepts list weakest first endpoint
150. mastery dashboard single endpoint
151. mastery history for charts
152. quiz should pick weakest concepts first
153. 80+ means mastered
154. show which doc gave which concept
155. doc delete should re-derive concepts
156. retry reprocessing should not double count mastery
157. concept chips colored by score
158. mastery bar animation on update
159. overall progress ring in project header
160. weak concepts section in dashboard
161. build adaptive quiz pipeline backend only first no endpoints
162. implement quiz backend + frontend integrate, read codebase carefully first, test correct wrong answers
163. full quiz feature flat routes sidebar tracker attempts dropdown
164. save and submit quiz full sequence upfront grounded docs, free navigation, submit evaluates all, results with feedback, plus project crud modals, plan properly no code in chat
165. for open-ended if not answer answer i get the 100 pass fix it
166. generate mcqs strictly from docs 4 options one correct
167. open ended questions with grading rubric
168. mcq eval exact match no llm
169. open ended eval with llm rubric score + feedback
170. partial credit 0 50 100 bands
171. quiz start builds full question plan upfront
172. save draft answers per question
173. submit all evaluates async updates mastery completes quiz
174. results page score per question feedback
175. quiz history list per project
176. previous attempts dropdown in results
177. adapt difficulty from earlier answers
178. completion writes mastery for all concepts
179. quiz needs name and learning goal fields
180. tracker dots without concept names
181. evaluating state after submit till scoring done
182. submitted quiz locked read only
183. delete quiz with questions attempts
184. validate all quiz payloads pydantic
185. quiz setup view with name goal
186. active quiz view one question at a time with save
187. next prev navigation free
188. submit quiz confirm modal
189. results view with score circle
190. correct answers green wrong red in review
191. explanation per question in review
192. retake quiz button creates new attempt
193. quiz timer optional per quiz
194. shuffle mcq options per attempt
195. require all answered before submit with warning
196. quiz instructions shown before start
197. start quiz button in workspace
198. quiz list with status completed pending
199. mastery change after quiz shown in results
200. weak concepts suggestion after low score
201. fix the assignment its not working properly make it work properly
202. assignment should be mcqs not single question, forget async, update frontend also
203. generate assignment from weakest concepts
204. assignment schemas with validation
205. evaluate assignment deterministic with feedback
206. track assignment attempts with scores
207. assignment list per project with status
208. assignment detail hide answer key before submit
209. delete assignment with questions submissions
210. order assignments newest first
211. results show correct answer explanation each
212. assignment outcomes update mastery like quiz
213. assignment setup view
214. assignment active view mcq cards
215. assignment submit confirm
216. assignment results view
217. assignment due display if set
218. assignment progress in project stats
219. copy assignment as new
220. assignment instructions block
221. event service with idempotency keys
222. activity feed endpoint paginated
223. emit ready failed events on ingestion finish
224. learning analytics summary per user
225. study streak from activity
226. per project progress single endpoint
227. mastery distribution buckets for charts
228. count ai calls per user project
229. aggregate scores averages trends
230. cap activity query limits
231. activity timeline ui in dashboard
232. streak flame widget
233. weekly study bar chart
234. average score card
235. docs read count stat
236. Build polished modern Admin Dashboard AI Learning Operations Center Overview Users Spaces Projects Activity Learning Analytics AI Usage AI Evaluation Background Processing System Health plus Login Register redesign Learn Practice Measure Grow identity
237. admin users table search pagination
238. admin user detail with spaces activity
239. admin all spaces projects overview counts
240. admin live activity with filters
241. admin charts signups active mastery distribution
242. admin ai usage per user project calls
243. admin evaluation averages pass rates
244. admin processing view statuses retry buttons
245. admin health cards db queue worker counts
246. admin sidebar layout
247. admin route guard role admin only
248. non admin hitting admin api gets 403
249. admin dashboard cards clickable to details
250. export users csv maybe later keep simple now
251. build frontend LMS dashboard React Redux Toolkit Framer Motion not chat assistant read backend first professional
252. fix frontend imports spaceProjectSlice tutorSlice resolve Materials AITutor verify frontend
253. redesign login register Learn Practice Measure Grow validated forms clear errors
254. app routing dashboard spaces workspace admin protected
255. redux store slices auth spaces materials tutor quiz admin
256. sidebar spaces nested projects active counts
257. space project crud modals with delete confirm
258. dashboard widgets progress recent weak concepts quick actions
259. project workspace tabs Materials Tutor Quiz Concepts Assignments
260. guard routes token 401 redirect login
261. central api client base url bearer token
262. skeleton loaders for lists chat quiz
263. empty states with next step buttons
264. toasts for all errors success consistent
265. responsive tablet mobile layouts
266. branded 404 page
267. replace emojis with svg icons everywhere
268. backend base url per env config
269. dark mode toggle later skip now keep light theme clean
270. keep css custom no ui library
271. materials drag drop browse upload validation messages
272. status badges queued processing ready failed each row
273. failure reason under doc with retry button
274. retry requeues without reupload
275. evidence viewer page excerpts
276. chat ui history citations suggestion chips
277. quiz setup active results attempts dropdown
278. mastery bars concept chips workspace
279. assignment mcq cards submit graded results
280. admin tables pagination search charts
281. activity timeline dashboard
282. all deletes ask confirm with item name
283. premium redesign senior designer no logic change design system layout sidebar dashboard workspace quiz step by step
284. enterprise redesign only css classnames wrappers no emoji svg icons 16px body premium sidebar light gray white indigo emerald soft shadows radii motion entrances overwrite all css
285. backend must return failures like clean api with limits never backend details log full server side only coded [E_AI_QUOTA] [E_TIMEOUT] [E_STORAGE] to client
286. inline field validation messages every form
287. upload timed out and cannot reach server messages with next steps
288. duplicate and not found copy naming the conflict
289. labels focus trap keyboard buttons accessible
290. end to end walk auth space project upload tutor quiz admin fix all found
291. quiz feedback should reference page source
292. tutor should remember learning_goal of project
293. concepts should update after each quiz not only at end
294. assignment mcq should shuffle options
295. dashboard should show continue learning card
296. materials search by filename
297. filter docs by status ready failed
298. sort quizzes by score
299. show best score per quiz in list
300. onboarding empty space wizard create space project upload doc
