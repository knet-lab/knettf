import os
import sys
from django.apps import AppConfig


_NO_BRIDGE_COMMANDS = {
    "migrate", "makemigrations", "showmigrations", "sqlmigrate",
    "shell", "shell_plus", "dbshell",
    "createsuperuser", "collectstatic",
    "check", "test", "inspectdb",
}


def _should_start_bridge() -> bool:
    argv = sys.argv
    if not argv:
        return False

    if len(argv) >= 2:
        cmd = argv[1]
        if cmd in _NO_BRIDGE_COMMANDS:
            return False
        if cmd == "runserver":
            # Django autoreloader spawns a child with RUN_MAIN=true.
            # Only start bridge in the child to avoid double-start.
            return os.environ.get("RUN_MAIN") == "true"

    # daphne / uvicorn / gunicorn launched directly (no autoreloader)
    prog = argv[0]
    for server in ("daphne", "uvicorn", "gunicorn"):
        if server in prog:
            return True

    return False


class VigilConfig(AppConfig):
    name = "vigil"

    def ready(self):
        if not _should_start_bridge():
            return

        from django.conf import settings
        base_url = getattr(settings, "VIGIL_BRIDGE_URL", "http://localhost:8080")
        token    = getattr(settings, "VIGIL_BRIDGE_TOKEN", None)

        from vigil import bridge
        bridge.start(base_url=base_url, token=token)
