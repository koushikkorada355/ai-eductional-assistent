from app.config import settings
from langchain_groq import ChatGroq
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

def get_llm():
    if settings.GROQ_API_KEY:
        return ChatGroq(model=settings.GROQ_MODEL, temperature=0.7, groq_api_key=settings.GROQ_API_KEY)
    # Dev note: Model not connected - set GROQ_API_KEY in .env
    return FakeMessagesListChatModel(responses=[AIMessage(content="AI tutor is temporarily unavailable. Please try again later.")])
