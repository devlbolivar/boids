from app.workers.celery_app import celery

@celery.task(name="health.ping", queue="orchestrator")
def ping(message: str = "pong") -> dict:
    return {"status": "ok", "echo": message}
