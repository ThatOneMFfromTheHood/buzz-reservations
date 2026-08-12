"""Public / guest endpoints (ТЗ §7)."""
from datetime import date as date_type

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import availability, services
from ..db import get_db
from ..models import Venue
from ..schemas import (AvailabilityOut, BookingConfigOut, CancelResult,
                       ReservationCreate, ReservationOut, SlotOut)
from ..security import guard_reservation_create, optional_user, verify_captcha
from ..services import BookingError

router = APIRouter(tags=["public"])


def _http(e: BookingError) -> HTTPException:
    return HTTPException(e.http, detail={"code": e.code, "message": e.message})


def get_venue(venue_id: int, db: Session) -> Venue:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(404, detail={"code": "venue_not_found", "message": "Venue not found"})
    return venue


def booking_config(db: Session, venue: Venue) -> BookingConfigOut:
    try:
        s = services.get_settings(db, venue.id)
    except BookingError as e:
        raise _http(e)
    return BookingConfigOut(
        venue_id=venue.id, venue_name=venue.name, address=venue.address,
        booking_enabled=s.booking_enabled, confirmation_mode=s.confirmation_mode,
        min_party_size=s.min_party_size, max_party_size=s.max_party_size,
        slot_step_min=s.slot_step_min, booking_duration_min=s.booking_duration_min,
        advance_booking_days=s.advance_booking_days, cancellation_hours=s.cancellation_hours,
        phone=s.phone, timezone=venue.timezone)


@router.get("/venues/{venue_id}/booking-config", response_model=BookingConfigOut)
def get_booking_config(venue_id: int, db: Session = Depends(get_db)):
    return booking_config(db, get_venue(venue_id, db))


@router.get("/venues/{venue_id}/availability", response_model=AvailabilityOut)
def get_availability(venue_id: int,
                     date: date_type = Query(...),
                     party_size: int = Query(..., ge=1, le=100),
                     db: Session = Depends(get_db)):
    venue = get_venue(venue_id, db)
    try:
        s = services.get_settings(db, venue.id)
    except BookingError as e:
        raise _http(e)
    slots = []
    if s.booking_enabled and s.min_party_size <= party_size <= s.max_party_size:
        slots = availability.day_slots(db, venue, s, date, party_size)
    return AvailabilityOut(
        date=date.isoformat(), party_size=party_size,
        slots=[SlotOut(time=sl.local_label, starts_at=sl.starts_at_utc,
                       free_tables=sl.free_tables) for sl in slots])


@router.post("/venues/{venue_id}/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(venue_id: int, payload: ReservationCreate, request: Request,
                       db: Session = Depends(get_db),
                       user_id: int | None = Depends(optional_user),
                       idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    venue = get_venue(venue_id, db)
    guard_reservation_create(request, payload.guest_phone, payload.guest_email)
    if not verify_captcha(payload.captcha_token):
        raise HTTPException(400, detail={"code": "captcha_failed", "message": "Captcha verification failed"})
    try:
        return services.create_reservation(db, venue, payload,
                                           guest_user_id=user_id,
                                           idempotency_key=idempotency_key)
    except BookingError as e:
        db.rollback()
        raise _http(e)


@router.get("/reservations/{reservation_id}", response_model=ReservationOut)
def get_reservation(reservation_id: int, code: str = Query(...), db: Session = Depends(get_db)):
    try:
        return services.get_by_code(db, reservation_id, code)
    except BookingError as e:
        raise _http(e)


@router.post("/reservations/{reservation_id}/cancel", response_model=CancelResult)
def cancel_reservation(reservation_id: int, code: str = Query(...), db: Session = Depends(get_db)):
    try:
        res = services.get_by_code(db, reservation_id, code)
        res = services.cancel_by_guest(db, res)
        return CancelResult(id=res.id, status=res.status)
    except BookingError as e:
        db.rollback()
        raise _http(e)
