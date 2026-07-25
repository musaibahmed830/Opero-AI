from opero_worker.celery_app import app


@app.task(name="opero_worker.ping")
def ping() -> str:
    """Proves the broker connection + task-execution loop end to end. Real
    background jobs (document embedding, mail polling, digest generation)
    replace/join this as the features that need them ship.
    """
    return "pong"
