"""Anti-abuse + auth stubs (ТЗ §12).

- Rate limit: in-memory sliding window per key (IP / phone / email). Good
  enough for a prototype and single process; production swaps this for Redis.
- CAPTCHA: hook that always passes in dev; production wires
  reCAPTCHA/Turnstile verification here.
- Admin auth: X-Admin-Token stub. INTEGRATION POINT — replace with the
  existing BUZZ admin auth (открытый вопрос №6 из ТЗ) and scope venue access
  by the authenticated admin's venue.
"""
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

ADMIN_TOKEN = os.environ.get("BUZZ_ADMIN_TOKEN", "dev-admin")
RATE_LIMIT_DISABLED = os.environ.get("BUZZ_RATE_LIMIT_DISABLED") == "1"

_lock = threading.Lock()
_hits: dict[str, deque] = defaultdict(deque)


def check_rate(key: str, limit: int, window_sec: int) -> None:
    if RATE_LIMIT_DISABLED:
        return
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] < now - window_sec:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, detail={"code": "rate_limited",
                                             "message": "Too many requests, try again later"})
        q.append(now)


def guard_reservation_create(request: Request, phone: str, email: str) -> None:
    ip = request.client.host if request.client else "?"
    check_rate(f"ip:{ip}", limit=10, window_sec=600)
    if phone:
        check_rate(f"phone:{phone}", limit=5, window_sec=3600)
    if email:
        check_rate(f"email:{email}", limit=5, window_sec=3600)


def verify_captcha(token: str | None) -> bool:
    # dev: pass-through; production: call reCAPTCHA/Turnstile verify API
    return True


def require_admin(x_admin_token: str = Header(default="")) -> str:
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, detail={"code": "unauthorized", "message": "Invalid admin token"})
    return x_admin_token


def optional_user(x_user_id: str = Header(default="")) -> int | None:
    """Stub for the app's user token. INTEGRATION POINT — replace with the
    existing BUZZ user auth; header carries the user id in the prototype."""
    return int(x_user_id) if x_user_id.isdigit() else None
