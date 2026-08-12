"""Background jobs (ТЗ §11). In the prototype they run on a thread timer inside
the API process and can be triggered manually via POST /admin/run-jobs.
Production: separate worker / cron on the same functions.
"""
import logging
import threading
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import notifications
from .db import SessionLocal
from .models import (Reservation, ReservationStatus, VenueBookingSettings, utcnow)

log = logging.getLogger("buzz.worker")
REMINDER_HOURS = 2


def expire_stale_pending(db: Session) -> int:
    """pending older than hold_pending_min -> cancelled_by_venue + notify."""
    n = 0
    rows = db.execute(
        select(Reservation, VenueBookingSettings.hold_pending_min)
        .join(VenueBookingSettings, VenueBookingSettings.venue_id == Reservation.venue_id)
        .where(Reservation.status == ReservationStatus.pending)
    ).all()
    now = utcnow()
    for res, hold_min in rows:
        if res.created_at + timedelta(minutes=hold_min) < now:
            res.status = ReservationStatus.cancelled_by_venue
            res.cancelled_at = now
            db.commit()
            notifications.on_status_change(db, res, "expired")
            n += 1
    return n


def send_reminders(db: Session) -> int:
    """One reminder REMINDER_HOURS before start; outbox dedupe keeps it single."""
    from .models import NotificationOutbox
    now = utcnow()
    horizon = now + timedelta(hours=REMINDER_HOURS)
    rows = db.scalars(select(Reservation).where(
        Reservation.status == ReservationStatus.confirmed,
        Reservation.starts_at > now,
        Reservation.starts_at <= horizon)).all()
    n = 0
    for res in rows:
        sent = db.scalar(select(NotificationOutbox.id).where(
            NotificationOutbox.reservation_id == res.id,
            NotificationOutbox.event == "reminder").limit(1))
        if not sent:
            notifications.reminder(db, res)
            n += 1
    return n


def complete_past(db: Session) -> int:
    """confirmed whose end has passed -> completed (for stats)."""
    now = utcnow()
    rows = db.scalars(select(Reservation).where(
        Reservation.status == ReservationStatus.confirmed,
        Reservation.ends_at < now)).all()
    for res in rows:
        res.status = ReservationStatus.completed
    if rows:
        db.commit()
    return len(rows)


def run_all() -> dict:
    db = SessionLocal()
    try:
        result = {
            "expired_pending": expire_stale_pending(db),
            "reminders_sent": send_reminders(db),
            "completed": complete_past(db),
        }
        log.info("jobs: %s", result)
        return result
    finally:
        db.close()


def start_timer(interval_sec: int = 60) -> threading.Timer:
    def tick():
        try:
            run_all()
        except Exception:
            log.exception("background jobs failed")
        finally:
            start_timer(interval_sec)
    t = threading.Timer(interval_sec, tick)
    t.daemon = True
    t.start()
    return t
