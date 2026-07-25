from opero_worker.celery_app import app
from opero_worker.tasks import ping


def test_ping_task_is_registered() -> None:
    assert "opero_worker.ping" in app.tasks


def test_ping_task_runs_and_returns_pong() -> None:
    app.conf.task_always_eager = True
    try:
        result = ping.delay()
        assert result.get(timeout=5) == "pong"
    finally:
        app.conf.task_always_eager = False
