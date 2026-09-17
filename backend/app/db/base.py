# Import all models to ensure Base.metadata.create_all picks them up
from app.db.models.user import User  # noqa: F401
from app.db.models.space import Space  # noqa: F401
from app.db.models.project import Project  # noqa: F401
from app.db.models.chat import ChatSession, Message  # noqa: F401
from app.db.models.document import Document, DocumentChunk  # noqa: F401
from app.db.models.assessment import Concept, Quiz, QuizQuestion, Assignment, AssignmentQuestion, AssignmentSubmission  # noqa: F401
from app.db.models.mastery import UserConceptMastery, QuizHistory, MasteryHistory  # noqa: F401
from app.db.models.learning import LearningContext, ConversationSummary  # noqa: F401
