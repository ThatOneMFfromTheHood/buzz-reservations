"""Admin endpoints — extension of the existing venue admin panel (ТЗ §7).

Auth is the X-Admin-Token stub from security.py; INTEGRATION POINT — plug the
existing BUZZ admin auth in `require_admin` and scope by the admin's venue.
"""
from datetime import date as date_type, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import services
from ..db import get_db
from ..models import (Reservation, ReservationStatus, Venue, VenueBookingSettings,
                      VenueHours, VenueHoursOverride, VenueTable, WidgetConfig)
from ..schemas import (AdminReservationUpdate, BookingSettingsIn, BookingSettingsOut,
                       ConfirmIn, HoursIn, HoursOut, HoursOverrideIn, HoursOverrideOut,
                       ReservationOut, TableIn, TableOut, WidgetConfigIn)
from ..security import require_admin
from ..services import BookingError
from .public import get_venue

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _http(e: BookingError) -> HTTPException:
    return HTTPException(e.http, detail={"code": e.code, "message": e.message})


# --- venues (helper for the panel's venue picker) -------------------------------

@router.get("/venues")
def list_venues(db: Session = Depends(get_db)):
    """In the real BUZZ admin the venue comes from the session; prototype
    exposes a picker."""
    return [{"id": v.id, "name": v.name, "address": v.address}
            for v in db.scalars(select(Venue).order_by(Venue.id))]


# --- tables CRUD ---------------------------------------------------------------

@router.get("/venues/{venue_id}/tables", response_model=list[TableOut])
def list_tables(venue_id: int, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    return db.scalars(select(VenueTable).where(VenueTable.venue_id == venue_id)
                      .order_by(VenueTable.id)).all()


@router.post("/venues/{venue_id}/tables", response_model=TableOut, status_code=201)
def create_table(venue_id: int, payload: TableIn, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    t = VenueTable(venue_id=venue_id, **payload.model_dump())
    db.add(t)
    db.commit()
    return t


@router.put("/venues/{venue_id}/tables/{table_id}", response_model=TableOut)
def update_table(venue_id: int, table_id: int, payload: TableIn, db: Session = Depends(get_db)):
    t = db.get(VenueTable, table_id)
    if t is None or t.venue_id != venue_id:
        raise HTTPException(404, detail={"code": "table_not_found", "message": "Table not found"})
    for k, v in payload.model_dump().items():
        setattr(t, k, v)
    db.commit()
    return t


@router.delete("/venues/{venue_id}/tables/{table_id}", status_code=204)
def delete_table(venue_id: int, table_id: int, db: Session = Depends(get_db)):
    t = db.get(VenueTable, table_id)
    if t is None or t.venue_id != venue_id:
        raise HTTPException(404, detail={"code": "table_not_found", "message": "Table not found"})
    has_res = db.scalar(select(Reservation.id).where(Reservation.table_id == table_id).limit(1))
    if has_res:
        # keep history intact — soft-disable instead of hard delete
        t.is_active = False
        t.is_bookable = False
    else:
        db.delete(t)
    db.commit()


# --- booking settings ------------------------------------------------------------

@router.get("/venues/{venue_id}/booking-settings", response_model=BookingSettingsOut)
def get_settings(venue_id: int, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    try:
        return services.get_settings(db, venue_id)
    except BookingError as e:
        raise _http(e)


@router.put("/venues/{venue_id}/booking-settings", response_model=BookingSettingsOut)
def put_settings(venue_id: int, payload: BookingSettingsIn, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    s = db.scalar(select(VenueBookingSettings).where(VenueBookingSettings.venue_id == venue_id))
    if s is None:
        s = VenueBookingSettings(venue_id=venue_id)
        db.add(s)
    for k, v in payload.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return s


# --- hours + overrides ------------------------------------------------------------

@router.get("/venues/{venue_id}/hours", response_model=list[HoursOut])
def list_hours(venue_id: int, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    return db.scalars(select(VenueHours).where(VenueHours.venue_id == venue_id)
                      .order_by(VenueHours.weekday, VenueHours.open_time)).all()


@router.put("/venues/{venue_id}/hours", response_model=list[HoursOut])
def replace_hours(venue_id: int, payload: list[HoursIn], db: Session = Depends(get_db)):
    """Full replace — the admin UI edits the week as one document."""
    get_venue(venue_id, db)
    for row in db.scalars(select(VenueHours).where(VenueHours.venue_id == venue_id)):
        db.delete(row)
    rows = [VenueHours(venue_id=venue_id, **h.model_dump()) for h in payload]
    db.add_all(rows)
    db.commit()
    return rows


@router.get("/venues/{venue_id}/hours-override", response_model=list[HoursOverrideOut])
def list_overrides(venue_id: int, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    return db.scalars(select(VenueHoursOverride).where(VenueHoursOverride.venue_id == venue_id)
                      .order_by(VenueHoursOverride.date)).all()


@router.put("/venues/{venue_id}/hours-override", response_model=list[HoursOverrideOut])
def replace_overrides(venue_id: int, payload: list[HoursOverrideIn], db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    for row in db.scalars(select(VenueHoursOverride).where(VenueHoursOverride.venue_id == venue_id)):
        db.delete(row)
    rows = [VenueHoursOverride(venue_id=venue_id, **h.model_dump()) for h in payload]
    db.add_all(rows)
    db.commit()
    return rows


# --- reservations ------------------------------------------------------------------

@router.get("/venues/{venue_id}/reservations", response_model=list[ReservationOut])
def list_reservations(venue_id: int,
                      date: date_type | None = Query(default=None),
                      status: ReservationStatus | None = Query(default=None),
                      db: Session = Depends(get_db)):
    venue = get_venue(venue_id, db)
    stmt = select(Reservation).where(Reservation.venue_id == venue_id)
    if date is not None:
        tz = ZoneInfo(venue.timezone or "Europe/Riga")
        day_start = datetime.combine(date, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
        stmt = stmt.where(Reservation.starts_at >= day_start,
                          Reservation.starts_at < day_start + timedelta(days=1))
    if status is not None:
        stmt = stmt.where(Reservation.status == status)
    return db.scalars(stmt.order_by(Reservation.starts_at)).all()


def _get_res(db: Session, reservation_id: int) -> Reservation:
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "Reservation not found"})
    return res


@router.post("/reservations/{reservation_id}/confirm", response_model=ReservationOut)
def confirm(reservation_id: int, payload: ConfirmIn | None = None, db: Session = Depends(get_db)):
    try:
        return services.admin_confirm(db, _get_res(db, reservation_id),
                                      table_id=payload.table_id if payload else None)
    except BookingError as e:
        db.rollback()
        raise _http(e)


@router.post("/reservations/{reservation_id}/decline", response_model=ReservationOut)
def decline(reservation_id: int, db: Session = Depends(get_db)):
    try:
        return services.admin_decline(db, _get_res(db, reservation_id))
    except BookingError as e:
        db.rollback()
        raise _http(e)


@router.post("/reservations/{reservation_id}/no-show", response_model=ReservationOut)
def no_show(reservation_id: int, db: Session = Depends(get_db)):
    try:
        return services.admin_no_show(db, _get_res(db, reservation_id))
    except BookingError as e:
        db.rollback()
        raise _http(e)


@router.put("/reservations/{reservation_id}", response_model=ReservationOut)
def update_reservation(reservation_id: int, payload: AdminReservationUpdate,
                       db: Session = Depends(get_db)):
    res = _get_res(db, reservation_id)
    try:
        s = services.get_settings(db, res.venue_id)
    except BookingError as e:
        raise _http(e)
    data = payload.model_dump(exclude_unset=True)
    if "starts_at" in data and data["starts_at"] is not None:
        starts = data["starts_at"]
        if starts.tzinfo is not None:
            starts = starts.astimezone(timezone.utc).replace(tzinfo=None)
        res.starts_at = starts
        res.ends_at = starts + timedelta(minutes=s.booking_duration_min)
    if "party_size" in data and data["party_size"] is not None:
        res.party_size = data["party_size"]
    if "table_id" in data:
        res.table_id = data["table_id"]
    if "special_request" in data:
        res.special_request = data["special_request"]
    db.commit()
    return res


# --- widget config -------------------------------------------------------------------

@router.get("/venues/{venue_id}/widget-config", response_model=WidgetConfigIn)
def get_widget_config(venue_id: int, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    cfg = db.scalar(select(WidgetConfig).where(WidgetConfig.venue_id == venue_id))
    if cfg is None:
        raise HTTPException(404, detail={"code": "widget_not_found", "message": "Widget not configured"})
    return WidgetConfigIn(
        slug=cfg.slug, primary_color=cfg.primary_color, text_color=cfg.text_color,
        bg_color=cfg.bg_color, form_control_color=cfg.form_control_color, font=cfg.font,
        corner_style=cfg.corner_style, text_alignment=cfg.text_alignment,
        default_lang=cfg.default_lang, logo_url=cfg.logo_url,
        photo_url=cfg.photo_url, policy_text=cfg.policy_text,
        info_items=cfg.info_items or [])


@router.put("/venues/{venue_id}/widget-config", response_model=WidgetConfigIn)
def put_widget_config(venue_id: int, payload: WidgetConfigIn, db: Session = Depends(get_db)):
    get_venue(venue_id, db)
    taken = db.scalar(select(WidgetConfig).where(WidgetConfig.slug == payload.slug,
                                                 WidgetConfig.venue_id != venue_id))
    if taken:
        raise HTTPException(409, detail={"code": "slug_taken", "message": "Slug already in use"})
    cfg = db.scalar(select(WidgetConfig).where(WidgetConfig.venue_id == venue_id))
    if cfg is None:
        cfg = WidgetConfig(venue_id=venue_id, slug=payload.slug)
        db.add(cfg)
    data = payload.model_dump()
    data["info_items"] = [i if isinstance(i, dict) else i for i in data["info_items"]]
    for k, v in data.items():
        setattr(cfg, k, v)
    db.commit()
    return payload
