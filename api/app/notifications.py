"""Notification Service stub (ТЗ §10).

Prototype writes every message into `notification_outbox` and logs it.
Production: a worker drains the outbox into real channels (email/SMS/push)
so the booking flow is never blocked by a slow provider.
"""
import logging

from sqlalchemy.orm import Session

from .models import NotificationOutbox, Reservation, ReservationSource, utcnow

log = logging.getLogger("buzz.notifications")


def _queue(db: Session, res: Reservation | None, channel: str, recipient: str,
           event: str, payload: dict | None = None) -> None:
    row = NotificationOutbox(
        reservation_id=res.id if res else None,
        channel=channel, recipient=recipient, event=event, payload=payload or {},
        sent_at=utcnow(),  # prototype "sends" instantly by logging
    )
    db.add(row)
    db.commit()
    log.info("notify [%s->%s] %s res=%s payload=%s", channel, recipient, event,
             res.id if res else "-", payload)


def on_created(db: Session, res: Reservation, lang: str = "en") -> None:
    payload = {"code": res.confirmation_code, "status": res.status.value, "lang": lang}
    if res.guest_email:
        _queue(db, res, "email", res.guest_email, "created", payload)
    if res.source == ReservationSource.app and res.guest_user_id:
        _queue(db, res, "push", f"user:{res.guest_user_id}", "created", payload)
    # venue side: pending queue needs action in manual mode
    _queue(db, res, "admin", f"venue:{res.venue_id}", "created", payload)


def on_status_change(db: Session, res: Reservation, event: str) -> None:
    payload = {"code": res.confirmation_code, "status": res.status.value}
    if res.guest_email:
        _queue(db, res, "email", res.guest_email, event, payload)
    if res.source == ReservationSource.app and res.guest_user_id:
        _queue(db, res, "push", f"user:{res.guest_user_id}", event, payload)


def reminder(db: Session, res: Reservation) -> None:
    payload = {"code": res.confirmation_code, "starts_at": res.starts_at.isoformat()}
    if res.guest_email:
        _queue(db, res, "email", res.guest_email, "reminder", payload)
    if res.source == ReservationSource.app and res.guest_user_id:
        _queue(db, res, "push", f"user:{res.guest_user_id}", "reminder", payload)
