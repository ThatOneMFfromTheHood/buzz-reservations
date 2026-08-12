"""Acceptance-criteria tests (ТЗ §14)."""
import threading
from datetime import datetime, timedelta, timezone

from zoneinfo import ZoneInfo

from conftest import ADMIN

RIGA = ZoneInfo("Europe/Riga")
RIVIERA = 1  # auto-confirm, 7 tables
GONGU = 2    # manual-confirm, 4 tables (2x2 + 2x4), max_party 4


def future_date(days=7):
    return (datetime.now(RIGA) + timedelta(days=days)).date()


def get_slot(client, venue_id=RIVIERA, party=2, days=7, idx=0):
    date = future_date(days).isoformat()
    r = client.get(f"/venues/{venue_id}/availability",
                   params={"date": date, "party_size": party})
    assert r.status_code == 200, r.text
    slots = r.json()["slots"]
    assert slots, f"no slots on {date}"
    return slots[idx]


def make_booking(client, venue_id=RIVIERA, party=2, days=7, idx=0, **over):
    slot = get_slot(client, venue_id, party, days, idx)
    body = {"party_size": party, "starts_at": slot["starts_at"],
            "guest_name": "Test Guest", "guest_phone": "+371 20000000",
            "guest_email": "guest@example.com", "source": "widget", **over}
    return client.post(f"/venues/{venue_id}/reservations", json=body), slot


# --- availability -----------------------------------------------------------

def test_availability_grid(client):
    slot = get_slot(client)
    assert slot["time"] == "12:00"
    r = client.get(f"/venues/{RIVIERA}/availability",
                   params={"date": future_date().isoformat(), "party_size": 2})
    times = [s["time"] for s in r.json()["slots"]]
    assert "12:30" in times and "21:00" in times
    assert "21:30" not in times  # close 23:00 - 120min duration


def test_availability_respects_capacity(client):
    # GONGU: party of 4 -> only two 4-tops fit
    slot = get_slot(client, GONGU, party=4)
    assert slot["free_tables"] == 2


def test_gongu_split_hours(client):
    r = client.get(f"/venues/{GONGU}/availability",
                   params={"date": future_date().isoformat(), "party_size": 2})
    times = [s["time"] for s in r.json()["slots"]]
    assert "12:00" in times and "18:00" in times
    assert "15:30" not in times and "16:00" not in times  # gap between services


def test_min_capacity_first(client, db):
    """Party of 2 must take a 2-top, not burn the 4-top."""
    r, _ = make_booking(client, GONGU, party=2)
    assert r.status_code == 201, r.text
    from app.models import Reservation, VenueTable
    res = db.get(Reservation, r.json()["id"])
    assert db.get(VenueTable, res.table_id).capacity == 2


# --- booking flows ------------------------------------------------------------

def test_auto_confirm_flow(client):
    r, _ = make_booking(client, RIVIERA)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "confirmed"
    assert len(data["confirmation_code"]) == 6
    # guest can read it back by code
    g = client.get(f"/reservations/{data['id']}", params={"code": data["confirmation_code"]})
    assert g.status_code == 200 and g.json()["status"] == "confirmed"


def test_manual_flow_pending_then_confirm(client):
    r, _ = make_booking(client, GONGU, party=2)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    c = client.post(f"/admin/reservations/{data['id']}/confirm", headers=ADMIN, json={})
    assert c.status_code == 200 and c.json()["status"] == "confirmed"


def test_manual_flow_decline(client):
    r, _ = make_booking(client, GONGU, party=2)
    d = client.post(f"/admin/reservations/{r.json()['id']}/decline", headers=ADMIN)
    assert d.status_code == 200 and d.json()["status"] == "cancelled_by_venue"


def test_party_too_large_gives_call_message(client):
    slot = get_slot(client, GONGU, party=2)
    body = {"party_size": 5, "starts_at": slot["starts_at"], "guest_name": "Big Group",
            "guest_phone": "+371 20000001", "source": "widget"}
    r = client.post(f"/venues/{GONGU}/reservations", json=body)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == "party_too_large"
    assert "+371 20569922" in detail["message"]


def test_guest_cancel_within_window(client):
    r, _ = make_booking(client, RIVIERA, days=7)
    data = r.json()
    c = client.post(f"/reservations/{data['id']}/cancel",
                    params={"code": data["confirmation_code"]})
    assert c.status_code == 200 and c.json()["status"] == "cancelled_by_guest"
    # cancelled slot frees the table again
    r2, _ = make_booking(client, RIVIERA, days=7)
    assert r2.status_code == 201


def test_idempotency_key(client):
    slot = get_slot(client)
    body = {"party_size": 2, "starts_at": slot["starts_at"], "guest_name": "Idem",
            "guest_email": "i@example.com", "source": "widget"}
    h = {"Idempotency-Key": "abc-123"}
    r1 = client.post(f"/venues/{RIVIERA}/reservations", json=body, headers=h)
    r2 = client.post(f"/venues/{RIVIERA}/reservations", json=body, headers=h)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


# --- double booking (acceptance №4) --------------------------------------------

def test_tables_exhaust_then_conflict(client):
    """GONGU has exactly two 2-tops; a party of 2 can also take the two 4-tops.
    Bookings 1-4 succeed, booking 5 on the same slot -> 409."""
    slot = get_slot(client, GONGU, party=2)
    body = {"party_size": 2, "starts_at": slot["starts_at"], "guest_name": "G",
            "guest_email": "x@example.com", "source": "widget"}
    codes = [client.post(f"/venues/{GONGU}/reservations", json=body).status_code
             for _ in range(5)]
    assert codes[:4] == [201, 201, 201, 201]
    assert codes[4] == 409
    # and the slot disappears from availability
    r = client.get(f"/venues/{GONGU}/availability",
                   params={"date": future_date().isoformat(), "party_size": 2})
    assert slot["time"] not in [s["time"] for s in r.json()["slots"]]


def test_concurrent_double_booking(client):
    """20 parallel requests fight for 4 tables -> exactly 4 win."""
    slot = get_slot(client, GONGU, party=2, days=8)
    results = []
    lock = threading.Lock()

    def hit(i):
        body = {"party_size": 2, "starts_at": slot["starts_at"],
                "guest_name": f"Racer {i}", "guest_email": f"r{i}@example.com",
                "source": "widget"}
        r = client.post(f"/venues/{GONGU}/reservations", json=body)
        with lock:
            results.append(r.status_code)

    threads = [threading.Thread(target=hit, args=(i,)) for i in range(20)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert results.count(201) == 4, f"expected 4 winners, got {results}"
    assert results.count(409) == 16


# --- validation edges ------------------------------------------------------------

def test_cannot_book_past_or_off_grid(client):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    body = {"party_size": 2, "starts_at": past, "guest_name": "Ghost",
            "guest_email": "g@example.com", "source": "widget"}
    assert client.post(f"/venues/{RIVIERA}/reservations", json=body).status_code == 400

    slot = get_slot(client)
    off = (datetime.fromisoformat(slot["starts_at"]) + timedelta(minutes=7)).isoformat()
    body["starts_at"] = off
    r = client.post(f"/venues/{RIVIERA}/reservations", json=body)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "outside_hours"


def test_hours_override_closes_day(client):
    date = future_date(9).isoformat()
    r = client.put(f"/admin/venues/{RIVIERA}/hours-override", headers=ADMIN,
                   json=[{"date": date, "is_closed": True}])
    assert r.status_code == 200
    a = client.get(f"/venues/{RIVIERA}/availability",
                   params={"date": date, "party_size": 2})
    assert a.json()["slots"] == []


# --- worker ------------------------------------------------------------------------

def test_stale_pending_expires(client, db):
    r, _ = make_booking(client, GONGU, party=2)
    res_id = r.json()["id"]
    from datetime import datetime as dt
    from app.models import Reservation
    from app import worker
    row = db.get(Reservation, res_id)
    row.created_at = row.created_at - timedelta(minutes=999)
    db.commit()
    result = worker.run_all()
    assert result["expired_pending"] >= 1
    db.expire_all()
    assert db.get(Reservation, res_id).status.value == "cancelled_by_venue"


# --- widget config -------------------------------------------------------------------

def test_widget_config(client):
    r = client.get("/widget/riviera/config")
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["venue_name"] == "RIVIERA restaurant"
    assert cfg["booking"]["confirmation_mode"] == "auto"
    assert len(cfg["info_items"]) == 10
    assert client.get("/widget/nope/config").status_code == 404
