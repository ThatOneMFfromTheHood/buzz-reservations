"""Reservation lifecycle: create (with conflict control), cancel, confirm, decline.

Double-booking safety (ТЗ 6.4): availability check + insert run inside ONE
transaction. On PostgreSQL the overlap check locks rows via FOR UPDATE; on
SQLite the engine issues BEGIN IMMEDIATE for writers, so the whole
check-then-insert is serialized. Losers get ConflictError -> HTTP 409.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import availability, notifications
from .models import (ConfirmationMode, IdempotencyKey, Reservation,
                     ReservationSource, ReservationStatus, Venue,
                     VenueBookingSettings, utcnow)
from .schemas import ReservationCreate

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L


class BookingError(Exception):
    def __init__(self, code: str, message: str, http: int = 400):
        self.code, self.message, self.http = code, message, http


class ConflictError(BookingError):
    def __init__(self, message="Slot was just taken, please pick another time"):
        super().__init__("slot_conflict", message, http=409)


def gen_code(db: Session) -> str:
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
        if not db.scalar(select(Reservation.id).where(Reservation.confirmation_code == code)):
            return code
    raise RuntimeError("could not generate unique confirmation code")


def get_settings(db: Session, venue_id: int) -> VenueBookingSettings:
    s = db.scalar(select(VenueBookingSettings).where(VenueBookingSettings.venue_id == venue_id))
    if s is None:
        raise BookingError("not_configured", "Booking is not configured for this venue", http=404)
    return s


def _validate_slot(db: Session, venue: Venue, s: VenueBookingSettings,
                   starts_at_utc: datetime, party_size: int) -> None:
    if not s.booking_enabled:
        raise BookingError("disabled", "Online booking is disabled for this venue", http=403)
    if party_size < s.min_party_size:
        raise BookingError("party_too_small", f"Minimum party size is {s.min_party_size}")
    if party_size > s.max_party_size:
        raise BookingError("party_too_large",
                           f"For groups over {s.max_party_size} please call the restaurant {s.phone}".strip())
    now = utcnow()
    if starts_at_utc - timedelta(minutes=s.min_lead_time_min) < now:
        raise BookingError("too_late", "This time can no longer be booked online")
    tz = ZoneInfo(venue.timezone or "Europe/Riga")
    local = starts_at_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    today_local = datetime.now(tz).date()
    if local.date() > today_local + timedelta(days=s.advance_booking_days):
        raise BookingError("too_far", f"Bookings open {s.advance_booking_days} days in advance")
    # slot must sit on the venue's slot grid inside working hours
    intervals = availability.working_intervals(db, venue.id, local.date())
    duration = timedelta(minutes=s.booking_duration_min)
    on_grid = False
    for open_t, close_t in intervals:
        cur = datetime.combine(local.date(), open_t, tzinfo=tz)
        last = datetime.combine(local.date(), close_t, tzinfo=tz) - duration
        while cur <= last:
            if cur == local:
                on_grid = True
                break
            cur += timedelta(minutes=s.slot_step_min)
        if on_grid:
            break
    if not on_grid:
        raise BookingError("outside_hours", "Selected time is outside bookable hours")


def create_reservation(db: Session, venue: Venue, payload: ReservationCreate,
                       guest_user_id: int | None = None,
                       idempotency_key: str | None = None) -> Reservation:
    # idempotent replay (ТЗ §12): same key returns the original reservation
    if idempotency_key:
        existing = db.scalar(select(IdempotencyKey).where(IdempotencyKey.key == idempotency_key))
        if existing:
            return db.get(Reservation, existing.reservation_id)

    s = get_settings(db, venue.id)
    starts_at_utc = payload.starts_at
    if starts_at_utc.tzinfo is not None:
        starts_at_utc = starts_at_utc.astimezone(timezone.utc).replace(tzinfo=None)
    _validate_slot(db, venue, s, starts_at_utc, payload.party_size)

    if not payload.guest_phone and not payload.guest_email:
        raise BookingError("contact_required", "Phone or email is required")

    # --- critical section: check + insert in one transaction ---
    # SQLite: writers are serialized by BEGIN IMMEDIATE (db.py).
    # PostgreSQL: FOR UPDATE alone can't stop two inserts into a table with
    # no existing rows to lock (phantom), so serialize bookings per venue
    # with a transaction-scoped advisory lock. v1-scale safe; the documented
    # upgrade path is an exclusion constraint on (table_id, tstzrange).
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text
        db.execute(text("select pg_advisory_xact_lock(:key)"), {"key": venue.id})

    table = availability.free_table_for(
        db, venue.id, payload.party_size, starts_at_utc,
        s.booking_duration_min, for_update=True)
    if table is None:
        raise ConflictError()

    auto = s.confirmation_mode == ConfirmationMode.auto
    res = Reservation(
        venue_id=venue.id,
        table_id=table.id,
        guest_user_id=guest_user_id,
        guest_name=payload.guest_name.strip(),
        guest_phone=payload.guest_phone,
        guest_email=payload.guest_email,
        party_size=payload.party_size,
        starts_at=starts_at_utc,
        ends_at=starts_at_utc + timedelta(minutes=s.booking_duration_min),
        status=ReservationStatus.confirmed if auto else ReservationStatus.pending,
        source=payload.source,
        special_request=payload.special_request,
        confirmation_code=gen_code(db),
        confirmed_at=utcnow() if auto else None,
    )
    db.add(res)
    db.flush()
    if idempotency_key:
        db.add(IdempotencyKey(key=idempotency_key, reservation_id=res.id))
    db.commit()

    notifications.on_created(db, res, lang=payload.lang)
    return res


def get_by_code(db: Session, reservation_id: int, code: str) -> Reservation:
    res = db.get(Reservation, reservation_id)
    if res is None or res.confirmation_code != (code or "").strip().upper():
        raise BookingError("not_found", "Reservation not found", http=404)
    return res


def cancel_by_guest(db: Session, res: Reservation) -> Reservation:
    if res.status in (ReservationStatus.cancelled_by_guest, ReservationStatus.cancelled_by_venue):
        return res
    if res.status in (ReservationStatus.completed, ReservationStatus.no_show):
        raise BookingError("finished", "Reservation is already in the past")
    s = get_settings(db, res.venue_id)
    if utcnow() > res.starts_at - timedelta(hours=s.cancellation_hours):
        raise BookingError(
            "too_late_to_cancel",
            f"Free cancellation closes {s.cancellation_hours}h before the visit — please call {s.phone}".strip())
    res.status = ReservationStatus.cancelled_by_guest
    res.cancelled_at = utcnow()
    db.commit()
    notifications.on_status_change(db, res, "cancelled")
    return res


def admin_confirm(db: Session, res: Reservation, table_id: int | None = None) -> Reservation:
    if res.status != ReservationStatus.pending:
        raise BookingError("bad_status", f"Cannot confirm reservation in status {res.status.value}")
    s = get_settings(db, res.venue_id)
    if table_id is not None:
        res.table_id = table_id
    elif res.table_id is None:
        venue = db.get(Venue, res.venue_id)
        table = availability.free_table_for(
            db, venue.id, res.party_size, res.starts_at, s.booking_duration_min, for_update=True)
        if table is None:
            raise ConflictError("No free table left for this slot")
        res.table_id = table.id
    res.status = ReservationStatus.confirmed
    res.confirmed_at = utcnow()
    db.commit()
    notifications.on_status_change(db, res, "confirmed")
    return res


def admin_decline(db: Session, res: Reservation) -> Reservation:
    if res.status not in (ReservationStatus.pending, ReservationStatus.confirmed):
        raise BookingError("bad_status", f"Cannot decline reservation in status {res.status.value}")
    res.status = ReservationStatus.cancelled_by_venue
    res.cancelled_at = utcnow()
    db.commit()
    notifications.on_status_change(db, res, "declined")
    return res


def admin_no_show(db: Session, res: Reservation) -> Reservation:
    if res.status != ReservationStatus.confirmed:
        raise BookingError("bad_status", "Only confirmed reservations can be marked no-show")
    res.status = ReservationStatus.no_show
    db.commit()
    return res
