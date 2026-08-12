"""Slot availability engine — ТЗ section 6.

All computation happens in the venue's timezone; storage is UTC-naive.
Table pick is min-capacity-first so a party of 2 never burns an 8-top.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .models import Reservation, ReservationStatus, VenueBookingSettings, VenueHours, VenueHoursOverride, VenueTable

BLOCKING_STATUSES = (ReservationStatus.pending, ReservationStatus.confirmed)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@dataclass
class Slot:
    starts_at_utc: datetime      # naive UTC
    local_label: str             # "HH:MM" in venue tz
    free_tables: int


def working_intervals(db: Session, venue_id: int, day: date) -> list[tuple[time, time]]:
    """venue_hours by weekday, then venue_hours_override wins (ТЗ 6.2.1)."""
    ov = db.scalar(select(VenueHoursOverride).where(
        VenueHoursOverride.venue_id == venue_id,
        VenueHoursOverride.date == day.isoformat()))
    if ov is not None:
        if ov.is_closed or not ov.open_time or not ov.close_time:
            return []
        return [(_parse_hhmm(ov.open_time), _parse_hhmm(ov.close_time))]
    rows = db.scalars(select(VenueHours).where(
        VenueHours.venue_id == venue_id,
        VenueHours.weekday == day.weekday())).all()
    return sorted((_parse_hhmm(r.open_time), _parse_hhmm(r.close_time)) for r in rows)


def candidate_tables(db: Session, venue_id: int, party_size: int) -> list[VenueTable]:
    """Bookable active tables that fit the party, smallest first (ТЗ 6.2.4)."""
    return db.scalars(
        select(VenueTable)
        .where(VenueTable.venue_id == venue_id,
               VenueTable.is_active.is_(True),
               VenueTable.is_bookable.is_(True),
               VenueTable.capacity >= party_size)
        .order_by(VenueTable.capacity.asc(), VenueTable.id.asc())
    ).all()


def overlapping_reservations(db: Session, table_ids: list[int],
                             win_start: datetime, win_end: datetime) -> list[Reservation]:
    """Blocking reservations intersecting [win_start, win_end) on given tables."""
    if not table_ids:
        return []
    return db.scalars(
        select(Reservation).where(
            Reservation.table_id.in_(table_ids),
            Reservation.status.in_(BLOCKING_STATUSES),
            Reservation.starts_at < win_end,
            Reservation.ends_at > win_start)
    ).all()


def free_table_for(db: Session, venue_id: int, party_size: int,
                   starts_at_utc: datetime, duration_min: int,
                   for_update: bool = False) -> VenueTable | None:
    """Smallest fitting table with no overlap on [start, start+duration).

    for_update=True locks matching reservation rows on PostgreSQL
    (SELECT ... FOR UPDATE); on SQLite the surrounding BEGIN IMMEDIATE
    transaction already serializes writers.
    """
    ends_at = starts_at_utc + timedelta(minutes=duration_min)
    tables = candidate_tables(db, venue_id, party_size)
    if not tables:
        return None
    stmt = select(Reservation.table_id).where(
        Reservation.table_id.in_([t.id for t in tables]),
        Reservation.status.in_(BLOCKING_STATUSES),
        Reservation.starts_at < ends_at,
        Reservation.ends_at > starts_at_utc)
    if for_update and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update()
    busy = set(db.scalars(stmt).all())
    for t in tables:
        if t.id not in busy:
            return t
    return None


def day_slots(db: Session, venue: models.Venue, settings: VenueBookingSettings,
              day: date, party_size: int) -> list[Slot]:
    """ТЗ 6.2 — full slot list for one date."""
    tz = ZoneInfo(venue.timezone or "Europe/Riga")
    now_utc = utcnow()
    today_local = datetime.now(tz).date()

    # advance window (6.2.3)
    if day < today_local or day > today_local + timedelta(days=settings.advance_booking_days):
        return []

    intervals = working_intervals(db, venue.id, day)
    if not intervals:
        return []

    tables = candidate_tables(db, venue.id, party_size)
    if not tables:
        return []
    table_ids = [t.id for t in tables]
    duration = timedelta(minutes=settings.booking_duration_min)
    step = timedelta(minutes=settings.slot_step_min)
    min_lead = timedelta(minutes=settings.min_lead_time_min)

    slots: list[Slot] = []
    for open_t, close_t in intervals:
        cur = datetime.combine(day, open_t, tzinfo=tz)
        last_start = datetime.combine(day, close_t, tzinfo=tz) - duration
        # one query per interval, overlap resolved in memory per slot
        win_start = cur.astimezone(timezone.utc).replace(tzinfo=None)
        win_end = (last_start + duration).astimezone(timezone.utc).replace(tzinfo=None)
        busy = overlapping_reservations(db, table_ids, win_start, win_end)
        while cur <= last_start:
            start_utc = cur.astimezone(timezone.utc).replace(tzinfo=None)
            if start_utc - min_lead >= now_utc:
                end_utc = start_utc + duration
                busy_tables = {r.table_id for r in busy
                               if r.starts_at < end_utc and r.ends_at > start_utc}
                free = [t for t in tables if t.id not in busy_tables]
                if free:
                    slots.append(Slot(
                        starts_at_utc=start_utc,
                        local_label=cur.strftime("%H:%M"),
                        free_tables=len(free)))
            cur += step
    return slots
