"""Vercel serverless entry for the BUZZ Reservations API.

The Angular SPA is served statically; vercel.json rewrites /api/* here.
The wrapper strips the /api prefix so FastAPI routes stay unprefixed.

DB: BUZZ_DB_URL env var, or a _config.py placed next to this file at deploy
time (kept out of git — holds the managed Postgres URL).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

try:
    from _config import DB_URL  # deploy-time secret, not in the repo
    os.environ.setdefault("BUZZ_DB_URL", DB_URL)
except ImportError:
    pass

from app.main import app as fastapi_app  # noqa: E402


class StripApiPrefix:
    """ASGI wrapper: /api/venues/... -> /venues/..."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").startswith("/api"):
            scope = dict(scope)
            scope["path"] = scope["path"][4:] or "/"
            raw = scope.get("raw_path")
            if raw:
                scope["raw_path"] = raw[4:] or b"/"
        await self.app(scope, receive, send)


app = StripApiPrefix(fastapi_app)
