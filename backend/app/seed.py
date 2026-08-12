"""Demo data: two venues styled after the reference screenshots —
RIVIERA (Tablein-like, auto-confirm) and GONGU (Tableo-like, manual confirm).
"""
from sqlalchemy import select

from .db import Base, SessionLocal, engine
from .models import (ConfirmationMode, CornerStyle, Venue, VenueBookingSettings,
                     VenueHours, VenueTable, WidgetConfig)

RIVIERA_POLICY = (
    "Please note that the duration of each reservation is a maximum of two hours. "
    "If you wish to remain longer, please contact us on +371 26605930\n\n"
    "Please note that we operate a 15-minute holding policy on reservations, if you are "
    "running late please call the team to let us know +371 26605930\n\n"
    "If you would like to book your favorite table or hall, please call the restaurant "
    "+371 26605930\n\n"
    "When you book a table via booking system, tables are automatically selected. "
    "If the restaurant is full, sometimes it's not possible to change a table.")

RIVIERA_INFO = [
    {"icon": "clock", "title": "Running Late", "text": "We hold reservation for 15 minutes"},
    {"icon": "child", "title": "Children", "text": "Children allowed"},
    {"icon": "dress", "title": "Dress Code", "text": "Smart Casual"},
    {"icon": "pets", "title": "Pets", "text": "Restricted"},
    {"icon": "lock", "title": "Secure reservation", "text": "For group bookings"},
    {"icon": "wheelchair", "title": "Wheelchair access", "text": "Wheelchair ramp"},
    {"icon": "group", "title": "Group reservations", "text": "Please call us"},
    {"icon": "cancel", "title": "Reservation cancellation", "text": "Up to 24 hours free"},
    {"icon": "bill", "title": "Bill", "text": "Cash and Card"},
    {"icon": "kitchen", "title": "Kitchen is open", "text": "1 hour before closing"},
]


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.scalar(select(Venue.id).limit(1)):
            return  # already seeded

        riviera = Venue(name="RIVIERA restaurant",
                        address="Dzirnavu iela 31, Centra rajons, Rīga, LV-1010",
                        timezone="Europe/Riga")
        gongu = Venue(name="GONGU", address="Gogoļa iela 1, Rīga, LV-1050",
                      timezone="Europe/Riga")
        db.add_all([riviera, gongu])
        db.flush()

        db.add_all([
            VenueBookingSettings(
                venue_id=riviera.id, confirmation_mode=ConfirmationMode.auto,
                booking_duration_min=120, slot_step_min=30, max_party_size=8,
                advance_booking_days=90, min_lead_time_min=60, hold_pending_min=15,
                phone="+371 26605930", cancellation_hours=24),
            VenueBookingSettings(
                venue_id=gongu.id, confirmation_mode=ConfirmationMode.manual,
                booking_duration_min=120, slot_step_min=30, max_party_size=4,
                advance_booking_days=60, min_lead_time_min=120, hold_pending_min=30,
                phone="+371 20569922", cancellation_hours=12),
        ])

        for venue, tables in (
            (riviera, [("T1", 2, "зал"), ("T2", 2, "зал"), ("T3", 4, "зал"),
                       ("T4", 4, "зал"), ("T5", 6, "зал"), ("Terase-1", 4, "терраса"),
                       ("Terase-2", 8, "терраса")]),
            (gongu, [("G1", 2, None), ("G2", 2, None), ("G3", 4, None), ("G4", 4, None)]),
        ):
            db.add_all([VenueTable(venue_id=venue.id, name=n, capacity=c, area=a)
                        for n, c, a in tables])

        # Mon-Sun 12:00-23:00 for RIVIERA; GONGU with lunch/dinner split
        for wd in range(7):
            db.add(VenueHours(venue_id=riviera.id, weekday=wd,
                              open_time="12:00", close_time="23:00"))
            db.add(VenueHours(venue_id=gongu.id, weekday=wd,
                              open_time="12:00", close_time="15:00"))
            db.add(VenueHours(venue_id=gongu.id, weekday=wd,
                              open_time="18:00", close_time="23:00"))

        # BUZZ-палитра по умолчанию (1:1 с debuzz-test.web.app); ресторан может
        # переопределить цвета в админке — white-label механика сохранена.
        db.add_all([
            WidgetConfig(venue_id=riviera.id, slug="riviera",
                         primary_color="#ff5934", text_color="#ffffff", bg_color="#191926",
                         form_control_color="#191926", font="system",
                         corner_style=CornerStyle.rounded, text_alignment="left",
                         default_lang="en", policy_text=RIVIERA_POLICY,
                         info_items=RIVIERA_INFO),
            WidgetConfig(venue_id=gongu.id, slug="gongu-riga-latvia",
                         primary_color="#ff5934", text_color="#ffffff", bg_color="#191926",
                         form_control_color="#191926", font="system",
                         corner_style=CornerStyle.rounded, text_alignment="left",
                         default_lang="ru",
                         policy_text="Если вы планируете бронирование для 5 и более человек, свяжитесь с нами: +371 20569922",
                         info_items=[]),
        ])
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
    print("seeded")
