from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "prnu_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.task_default_queue = "prnu"
