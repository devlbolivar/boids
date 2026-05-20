from celery import Celery
from app.config import settings

celery = Celery(
    "boids",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks.health", "app.workers.tasks.lead_finder"]
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Santiago",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.task_queues = {
    "orchestrator": {"exchange": "orchestrator"},
    "agents":       {"exchange": "agents"},
    "delivery":     {"exchange": "delivery"},
}
