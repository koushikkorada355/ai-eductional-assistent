ASSIGNMENT_MCQ_GENERATION_PROMPT = """You are an educational AI assistant. Generate {num_questions} multiple-choice questions (MCQs) about the given concepts, grounded in the context below.

Concepts: {concepts}

Context from study materials:
{context}

Instructions:
1. Each question must have exactly 4 options and exactly one correct answer.
2. The correct_answer must match one of the 4 options EXACTLY (character for character).
3. Spread questions across the listed concepts.
4. Keep questions clear, specific, and answerable from the context when possible.
5. Return ONLY a valid JSON array, no markdown, no extra text. Exact structure:
[
  {{"question_text": "...", "options": ["...", "...", "...", "..."], "correct_answer": "..."}}
]

JSON:
"""

ASSIGNMENT_OVERALL_FEEDBACK_PROMPT = """You are an educational AI assistant. A student scored {score} out of {total} on an MCQ assignment covering: {concepts}.

Per-question results:
{results}

Write exactly 2-3 encouraging, specific sentences: acknowledge what went well and what to review next. No JSON, just plain text.
"""
