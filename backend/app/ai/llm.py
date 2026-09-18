from app.config import settings
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from app.services.ai_usage_service import TrackedLLM

INCEPTION_MODEL_DEFAULT = "mercury-2.5"
INCEPTION_BASE_URL_DEFAULT = "https://api.inceptionlabs.ai/v1"


def get_llm():
    # Priority 1 (active): Inception Labs (Mercury, OpenAI-compatible API).
    # Key goes in .env as INCEPTION_API_KEY (see platform.inceptionlabs.ai).
    if settings.INCEPTION_API_KEY:
        inner = ChatOpenAI(
            model=settings.INCEPTION_MODEL or INCEPTION_MODEL_DEFAULT,
            temperature=0.7,
            api_key=settings.INCEPTION_API_KEY,
            base_url=settings.INCEPTION_BASE_URL or INCEPTION_BASE_URL_DEFAULT,
        )
    # Priority 2 (standby): Groq — kept as a working fallback, NOT removed.
    # Activate by setting GROQ_API_KEY in .env (currently commented out).
    elif settings.GROQ_API_KEY:
        inner = ChatGroq(model=settings.GROQ_MODEL, temperature=0.7, groq_api_key=settings.GROQ_API_KEY)
    else:
        # Dev note: Model not connected - set INCEPTION_API_KEY in .env
        inner = FakeMessagesListChatModel(responses=[AIMessage(content="AI tutor is temporarily unavailable. Please try again later.")])
    # Meter tokens/latency per call; transparent proxy, same interface.
    return TrackedLLM(inner)
