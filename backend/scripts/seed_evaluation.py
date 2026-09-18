"""Seed evaluation-style demo data for the Admin AI Evaluation dashboard.

Creates a self-contained demo slice (user -> space -> project -> concepts ->
chat messages with citations, quiz + graded questions, quiz history, AIUsage
rows) with created_at spread over the past 8 weeks so the 7d / 30d / All
filters and the Supported-rate-by-week chart all show real data.

Usage:
  docker compose exec -T backend python scripts/seed_evaluation.py [--force]

Idempotent: skips when the seed user already exists unless --force is given
(--force deletes the previous seed slice first). Never touches non-seed rows,
except backfilling legacy ai_usage rows stored with a blank provider.
"""
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/code")  # ensure `app` imports when run as scripts/seed_evaluation.py

from sqlalchemy import text

from app.db.session import SessionLocal
import app.db.base  # noqa: F401 — register models
from app.core.security import get_password_hash
from app.db.models.user import User
from app.db.models.space import Space
from app.db.models.project import Project
from app.db.models.assessment import Concept, Quiz, QuizQuestion
from app.db.models.chat import ChatSession, Message
from app.db.models.mastery import QuizHistory
from app.db.models.ai_usage import AIUsage

SEED_EMAIL = "eval.seed@local"
FORCE = "--force" in sys.argv
MODEL = "openai/gpt-oss-20b"
rng = random.Random(20260918)


def pct_days_ago(n):
    base = datetime.utcnow() - timedelta(days=n)
    return base.replace(hour=rng.randint(8, 20), minute=rng.randint(0, 59),
                        second=rng.randint(0, 59), microsecond=0)


def citation(i):
    return {"pdf_name": f"chapter-{(i % 3) + 1}.pdf",
            "page_number": (i * 7) % 40 + 1,
            "chunk_excerpt": f"Seed excerpt {i} grounding the tutor answer."}


def main() -> int:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == SEED_EMAIL).first()
        if existing is not None and not FORCE:
            print(f"[seed] seed user {SEED_EMAIL} already present — skipping (use --force to reseed).")
            return 0
        if existing is not None:
            print("[seed] --force: removing previous seed slice…")
            # Order matters for FKs (messages -> sessions -> project -> space -> user).
            space_ids = [s.id for s in db.query(Space).filter(Space.user_id == existing.id).all()]
            proj_ids = []
            if space_ids:
                proj_ids = [p.id for p in db.query(Project).filter(Project.space_id.in_(space_ids)).all()]
            if proj_ids:
                sess_ids = [s.id for s in db.query(ChatSession).filter(ChatSession.project_id.in_(proj_ids)).all()]
                if sess_ids:
                    db.query(Message).filter(Message.chat_session_id.in_(sess_ids)).delete(synchronize_session=False)
                    db.query(ChatSession).filter(ChatSession.id.in_(sess_ids)).delete(synchronize_session=False)
                quiz_ids = [q.id for q in db.query(Quiz).filter(Quiz.project_id.in_(proj_ids)).all()]
                if quiz_ids:
                    db.query(QuizQuestion).filter(QuizQuestion.quiz_id.in_(quiz_ids)).delete(synchronize_session=False)
                    db.query(Quiz).filter(Quiz.id.in_(quiz_ids)).delete(synchronize_session=False)
                db.query(Concept).filter(Concept.project_id.in_(proj_ids)).delete(synchronize_session=False)
                db.query(Project).filter(Project.id.in_(proj_ids)).delete(synchronize_session=False)
            db.query(Space).filter(Space.user_id == existing.id).delete(synchronize_session=False)
            db.query(QuizHistory).filter(QuizHistory.user_id == existing.id).delete(synchronize_session=False)
            db.query(AIUsage).filter(AIUsage.user_id == existing.id).delete(synchronize_session=False)
            db.query(User).filter(User.id == existing.id).delete(synchronize_session=False)
            db.commit()

        user = User(email=SEED_EMAIL, hashed_password=get_password_hash("seed-password"),
                    name="Eval Seed", role="user", is_active=True,
                    created_at=pct_days_ago(60))
        db.add(user)
        db.flush()

        space = Space(user_id=user.id, name="Eval Seed Space",
                      description="Seeded slice for the AI Evaluation dashboard.",
                      created_at=pct_days_ago(59))
        db.add(space)
        db.flush()

        project = Project(space_id=space.id, name="Eval Seed Project",
                          description="Seeded project", learning_goal="Demo evaluation signals",
                          overall_progress=62.5, created_at=pct_days_ago(58))
        db.add(project)
        db.flush()

        concepts = []
        for i, name in enumerate(["Photosynthesis", "Cellular Respiration", "Mitosis"]):
            c = Concept(project_id=project.id, name=name,
                        description=f"Seeded concept {name}.",
                        mastery_level=[72.0, 55.5, 38.0][i],
                        created_at=pct_days_ago(57 - i))
            db.add(c)
            concepts.append(c)
        db.flush()

        session = ChatSession(project_id=project.id, title="Seeded tutor thread",
                              created_at=pct_days_ago(56))
        db.add(session)
        db.flush()

        # 16 tutor turns spread over 8 weeks (2 per week): ~2/3 cited.
        answer_days = [55, 52, 48, 45, 41, 38, 34, 31, 27, 24, 20, 17, 13, 10, 6, 2]
        assistant_n = 0
        for idx, d in enumerate(answer_days):
            ts_q = pct_days_ago(d)
            ts_a = pct_days_ago(max(d - 1, 0))
            if ts_a < ts_q:
                ts_q, ts_a = ts_a, ts_q
            db.add(Message(chat_session_id=session.id, role="user",
                           content=f"Seeded learner question {idx + 1} about {concepts[idx % 3].name}?",
                           created_at=ts_q))
            cited = (idx % 3 != 2)  # every 3rd answer uncited -> unsupported/zero-context mix
            cites = [citation(idx * 2 + k) for k in range(rng.randint(1, 3))] if cited else []
            db.add(Message(chat_session_id=session.id, role="assistant",
                           content=(f"Seeded tutor answer {idx + 1} grounded in the material "
                                    f"[Source: Page {cites[0]['page_number']}]" if cites
                                    else f"Seeded general reply {idx + 1} (no retrieved context)."),
                           citations=cites, suggested_questions=[],
                           created_at=ts_a))
            assistant_n += 1
        db.flush()

        # Batch quiz: 12 MCQ (8 correct) + 6 open-ended incl. partial credit.
        quiz = Quiz(project_id=project.id, name="Seeded Quiz", goal="Seeded evaluation",
                    status="completed", created_at=pct_days_ago(15))
        db.add(quiz)
        db.flush()
        mcq_scores = [100] * 8 + [0] * 4
        rng.shuffle(mcq_scores)
        for i, score in enumerate(mcq_scores):
            concept = concepts[i % 3]
            correct = "Option A"
            db.add(QuizQuestion(
                quiz_id=quiz.id, concept_id=concept.id, question_type="multiple_choice",
                question_text=f"Seeded MCQ {i + 1} about {concept.name}?",
                options=["Option A", "Option B", "Option C", "Option D"],
                correct_answer=correct,
                user_answer=correct if score == 100 else "Option C",
                evaluation={"score": score,
                            "feedback": "Correct." if score == 100 else "Incorrect.",
                            "missing_concepts": [] if score == 100 else [concept.name]},
                created_at=pct_days_ago(15 - (i % 5))))
        open_scores = [85, 45, 70, 20, 90, 55]
        for i, score in enumerate(open_scores):
            concept = concepts[i % 3]
            db.add(QuizQuestion(
                quiz_id=quiz.id, concept_id=concept.id, question_type="open_ended",
                question_text=f"Seeded open question {i + 1} about {concept.name}?",
                options=None, correct_answer="Seeded ideal answer.",
                user_answer=f"Seeded learner response {i + 1}.",
                evaluation={"score": score, "feedback": f"Seeded feedback ({score}).",
                            "missing_concepts": [] if score >= 60 else [concept.name]},
                created_at=pct_days_ago(14 - (i % 5))))
        db.flush()

        # Adaptive-flow history (feeds verdict pass/fail alongside quiz scores).
        for i in range(10):
            concept = concepts[i % 3]
            ok = (i % 5 != 4)  # 8 pass / 2 fail
            db.add(QuizHistory(
                user_id=user.id, concept_id=concept.id,
                question_text=f"Seeded adaptive question {i + 1}?",
                question_type="MCQ" if i % 2 == 0 else "OPEN_ENDED",
                user_answer="Seeded answer", is_correct=ok,
                evaluator_feedback="Seeded correct." if ok else "Seeded incorrect.",
                created_at=pct_days_ago(12 - (i % 9))))
        db.flush()

        # Measured AIUsage rows (provider groq — never blank).
        usage_specs = [
            ("tutor_answer", 3, 9), ("tutor_answer", 2, 16), ("tutor_answer", 4, 23),
            ("tutor_answer", 3, 33), ("tutor_answer", 2, 47),
            ("quiz_generation", 1, 15), ("quiz_evaluation", 1, 14),
            ("concept_extraction", 1, 57), ("recommendations", 1, 11),
            ("recommendations", 1, 4), ("recommendations", 1, 26),
            ("summarization", 1, 30),
        ]
        for feat, calls, d in usage_specs:
            pt, ct = rng.randint(400, 1800), rng.randint(150, 900)
            lat = round(rng.uniform(600, 4200), 1)
            db.add(AIUsage(
                feature=feat, provider="groq", model=MODEL, latency_ms=lat,
                success=True, error=None, user_id=user.id, project_id=project.id,
                prompt_tokens=pt, completion_tokens=ct, total_tokens=pt + ct,
                cost_usd=round((pt * 0.59 + ct * 0.79) / 1_000_000, 6),
                calls=calls, created_at=pct_days_ago(d)))
        db.flush()

        # Backfill legacy ai_usage rows stored with a blank provider so the
        # AI Usage table never shows a missing provider name.
        fixed = db.execute(text(
            "UPDATE ai_usage SET provider = 'groq' "
            "WHERE (provider IS NULL OR provider = '') AND model = :model"
        ), {"model": MODEL}).rowcount
        db.commit()
        print(f"[seed] done: 1 user, 1 space, 1 project, 3 concepts, "
              f"{assistant_n} tutor answers, 18 quiz questions, 10 history rows, "
              f"{len(usage_specs)} usage rows. Backfilled {fixed} blank-provider usage rows.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
