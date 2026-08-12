"""Logical schema per ТЗ section 5.

NOTE ON INTEGRATION: `Venue` and `User` stand in for the entities that already
exist in the BUZZ system. When embedding into the real codebase, drop these two
tables and point the FKs at the existing ones (names to be aligned with the
current DB conventions — открытый вопрос №1 из ТЗ).
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ConfirmationMode(str, enum.Enum):
    auto = "auto"
    manual = "manual"


class ReservationStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled_by_guest = "cancelled_by_guest"
    cancelled_by_venue = "cancelled_by_venue"
    no_show = "no_show"
    completed = "completed"


class ReservationSource(str, enum.Enum):
    app = "app"
    widget = "widget"
    admin = "admin"


class CornerStyle(str, enum.Enum):
    rounded = "rounded"
    square = "square"


# --- stand-ins for existing BUZZ entities -----------------------------------

class Venue(Base):
    __tablename__ = "venues"  # EXISTING entity in BUZZ — reuse, do not duplicate
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(300), default="")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Riga")

    booking_settings: Mapped["VenueBookingSettings"] = relationship(back_populates="venue", uselist=False)
    tables: Mapped[list["VenueTable"]] = relationship(back_populates="venue")


class User(Base):
    __tablename__ = "users"  # EXISTING entity in BUZZ — reuse, do not duplicate
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(200), default="")


# --- 5.1 venue_booking_settings ----------------------------------------------

class VenueBookingSettings(Base):
    __tablename__ = "venue_booking_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), unique=True)
    booking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmation_mode: Mapped[ConfirmationMode] = mapped_column(
        Enum(ConfirmationMode), default=ConfirmationMode.auto)
    booking_duration_min: Mapped[int] = mapped_column(Integer, default=120)
    slot_step_min: Mapped[int] = mapped_column(Integer, default=30)
    max_party_size: Mapped[int] = mapped_column(Integer, default=8)
    min_party_size: Mapped[int] = mapped_column(Integer, default=1)
    advance_booking_days: Mapped[int] = mapped_column(Integer, default=60)
    min_lead_time_min: Mapped[int] = mapped_column(Integer, default=60)
    hold_pending_min: Mapped[int] = mapped_column(Integer, default=15)
    phone: Mapped[str] = mapped_column(String(40), default="")
    cancellation_hours: Mapped[int] = mapped_column(Integer, default=24)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    venue: Mapped[Venue] = relationship(back_populates="booking_settings")


# --- 5.2 venue_tables ---------------------------------------------------------

class VenueTable(Base):
    __tablename__ = "venue_tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    capacity: Mapped[int] = mapped_column(Integer)
    area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_bookable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    venue: Mapped[Venue] = relationship(back_populates="tables")


# --- 5.3 venue_hours (several rows per weekday = several service intervals) ---

class VenueHours(Base):
    __tablename__ = "venue_hours"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)  # 0=Mon .. 6=Sun
    open_time: Mapped[str] = mapped_column(String(5))   # "HH:MM"
    close_time: Mapped[str] = mapped_column(String(5))  # "HH:MM"


# --- 5.4 venue_hours_override --------------------------------------------------

class VenueHoursOverride(Base):
    __tablename__ = "venue_hours_override"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    date: Mapped[str] = mapped_column(String(10))  # "YYYY-MM-DD" in venue tz
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    open_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    close_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    __table_args__ = (UniqueConstraint("venue_id", "date"),)


# --- 5.5 reservations ----------------------------------------------------------

class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), index=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("venue_tables.id"), nullable=True)
    guest_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    guest_name: Mapped[str] = mapped_column(String(200))
    guest_phone: Mapped[str] = mapped_column(String(40), default="")
    guest_email: Mapped[str] = mapped_column(String(200), default="")
    party_size: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    ends_at: Mapped[datetime] = mapped_column(DateTime)                # UTC
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.pending, index=True)
    source: Mapped[ReservationSource] = mapped_column(Enum(ReservationSource))
    special_request: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmation_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_res_table_time", "table_id", "starts_at", "ends_at"),
    )


# --- 5.6 widget_configs ---------------------------------------------------------

class WidgetConfig(Base):
    __tablename__ = "widget_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), unique=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    primary_color: Mapped[str] = mapped_column(String(9), default="#ff5934")
    text_color: Mapped[str] = mapped_column(String(9), default="#191926")
    bg_color: Mapped[str] = mapped_column(String(9), default="#ffffff")
    form_control_color: Mapped[str] = mapped_column(String(9), default="#f0f0f0")
    font: Mapped[str] = mapped_column(String(80), default="Montserrat")
    corner_style: Mapped[CornerStyle] = mapped_column(Enum(CornerStyle), default=CornerStyle.rounded)
    text_alignment: Mapped[str] = mapped_column(String(10), default="left")
    default_lang: Mapped[str] = mapped_column(String(5), default="en")
    logo_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(400), nullable=True)  # обложка заведения
    policy_text: Mapped[str] = mapped_column(Text, default="")
    info_items: Mapped[list | None] = mapped_column(JSON, nullable=True)


# --- infrastructure: idempotency + notification outbox --------------------------

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    reservation_id: Mapped[int] = mapped_column(ForeignKey("reservations.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class NotificationOutbox(Base):
    """Queued notifications — prototype logs them; production hooks a real
    Notification Service (email/SMS/push) onto this outbox."""
    __tablename__ = "notification_outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int | None] = mapped_column(ForeignKey("reservations.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(20))    # email | sms | push | admin
    recipient: Mapped[str] = mapped_column(String(200))
    event: Mapped[str] = mapped_column(String(40))      # created | confirmed | declined | reminder | cancelled | expired
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
