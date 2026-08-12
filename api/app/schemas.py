"""Pydantic I/O schemas for the Reservations API."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import ConfirmationMode, CornerStyle, ReservationSource, ReservationStatus


# --- public ------------------------------------------------------------------

class BookingConfigOut(BaseModel):
    venue_id: int
    venue_name: str
    address: str
    booking_enabled: bool
    confirmation_mode: ConfirmationMode
    min_party_size: int
    max_party_size: int
    slot_step_min: int
    booking_duration_min: int
    advance_booking_days: int
    cancellation_hours: int
    phone: str
    timezone: str


class SlotOut(BaseModel):
    time: str                 # local "HH:MM"
    starts_at: datetime       # UTC
    free_tables: int


class AvailabilityOut(BaseModel):
    date: str
    party_size: int
    slots: list[SlotOut]


class ReservationCreate(BaseModel):
    party_size: int = Field(ge=1, le=100)
    starts_at: datetime
    guest_name: str = Field(min_length=1, max_length=200)
    guest_phone: str = Field(default="", max_length=40)
    guest_email: str = Field(default="", max_length=200)
    special_request: str | None = Field(default=None, max_length=2000)
    source: ReservationSource = ReservationSource.widget
    lang: str = "en"
    captcha_token: str | None = None  # verified by anti-bot hook (ТЗ §12)

    @field_validator("guest_phone", "guest_email")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ReservationOut(BaseModel):
    id: int
    venue_id: int
    status: ReservationStatus
    confirmation_code: str
    party_size: int
    starts_at: datetime
    ends_at: datetime
    guest_name: str
    guest_phone: str
    guest_email: str
    special_request: str | None
    source: ReservationSource
    table_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CancelResult(BaseModel):
    id: int
    status: ReservationStatus


# --- widget ------------------------------------------------------------------

class InfoItem(BaseModel):
    icon: str = ""
    title: str
    text: str = ""


class WidgetConfigOut(BaseModel):
    slug: str
    venue_id: int
    venue_name: str
    address: str
    primary_color: str
    text_color: str
    bg_color: str
    form_control_color: str
    font: str
    corner_style: CornerStyle
    text_alignment: str
    default_lang: str
    logo_url: str | None
    policy_text: str
    info_items: list[InfoItem]
    booking: BookingConfigOut


# --- admin -------------------------------------------------------------------

class TableIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    capacity: int = Field(ge=1, le=100)
    area: str | None = None
    is_active: bool = True
    is_bookable: bool = True


class TableOut(TableIn):
    id: int
    venue_id: int
    model_config = {"from_attributes": True}


class BookingSettingsIn(BaseModel):
    booking_enabled: bool = True
    confirmation_mode: ConfirmationMode = ConfirmationMode.auto
    booking_duration_min: int = Field(default=120, ge=15, le=600)
    slot_step_min: int = Field(default=30, ge=5, le=120)
    max_party_size: int = Field(default=8, ge=1, le=100)
    min_party_size: int = Field(default=1, ge=1, le=100)
    advance_booking_days: int = Field(default=60, ge=0, le=365)
    min_lead_time_min: int = Field(default=60, ge=0, le=10080)
    hold_pending_min: int = Field(default=15, ge=1, le=1440)
    phone: str = ""
    cancellation_hours: int = Field(default=24, ge=0, le=720)


class BookingSettingsOut(BookingSettingsIn):
    venue_id: int
    model_config = {"from_attributes": True}


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    open_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    close_time: str = Field(pattern=r"^\d{2}:\d{2}$")


class HoursOut(HoursIn):
    id: int
    model_config = {"from_attributes": True}


class HoursOverrideIn(BaseModel):
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    is_closed: bool = False
    open_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    close_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


class HoursOverrideOut(HoursOverrideIn):
    id: int
    model_config = {"from_attributes": True}


class WidgetConfigIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    primary_color: str = "#ff5934"
    text_color: str = "#191926"
    bg_color: str = "#ffffff"
    form_control_color: str = "#f0f0f0"
    font: str = "Montserrat"
    corner_style: CornerStyle = CornerStyle.rounded
    text_alignment: str = "left"
    default_lang: str = "en"
    logo_url: str | None = None
    policy_text: str = ""
    info_items: list[InfoItem] = []


class AdminReservationUpdate(BaseModel):
    starts_at: datetime | None = None
    party_size: int | None = Field(default=None, ge=1, le=100)
    table_id: int | None = None
    special_request: str | None = None


class ConfirmIn(BaseModel):
    table_id: int | None = None  # manual assignment; auto-picked when omitted
