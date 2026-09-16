from celery import Celery, Task
from loguru import logger
from app.config import settings

class BaseTask(Task):
    def __call__(self, *args, **kwargs):
        logger.info(f"Task starting: {self.name}")
        return super().__call__(*args, **kwargs)

    def on_success(self, retval, task_id, args, kwargs):
        logger.success(f"Task succeeded: {self.name} [{task_id}]")

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task failed: {self.name} [{task_id}] - {exc}")

celery_app = Celery(
    "ai_study_companion",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    task_cls=BaseTask,
    include=["app.tasks.document_tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    timezone="UTC",
    enable_utc=True,
)
