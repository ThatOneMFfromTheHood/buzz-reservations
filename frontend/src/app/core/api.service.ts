import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Availability, BookingConfig, BookingSettings, HoursOverride, Reservation,
  ReservationStatus, VenueHoursRow, VenueSummary, VenueTable, WidgetConfig,
  WidgetConfigAdmin,
} from './models';

/** Dev: the Angular dev-server proxies /api -> FastAPI :8000.
 *  Prod: the widget is served from the same domain as the API. */
const BASE = '/api';

export interface CreateReservationBody {
  party_size: number;
  starts_at: string;
  guest_name: string;
  guest_phone: string;
  guest_email: string;
  special_request?: string | null;
  source: 'app' | 'widget' | 'admin';
  lang?: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  // --- public ---------------------------------------------------------------
  bookingConfig(venueId: number): Observable<BookingConfig> {
    return this.http.get<BookingConfig>(`${BASE}/venues/${venueId}/booking-config`);
  }

  availability(venueId: number, date: string, partySize: number): Observable<Availability> {
    return this.http.get<Availability>(`${BASE}/venues/${venueId}/availability`, {
      params: { date, party_size: partySize },
    });
  }

  createReservation(venueId: number, body: CreateReservationBody,
                    idempotencyKey: string): Observable<Reservation> {
    return this.http.post<Reservation>(`${BASE}/venues/${venueId}/reservations`, body, {
      headers: { 'Idempotency-Key': idempotencyKey },
    });
  }

  getReservation(id: number, code: string): Observable<Reservation> {
    return this.http.get<Reservation>(`${BASE}/reservations/${id}`, { params: { code } });
  }

  cancelReservation(id: number, code: string): Observable<{ id: number; status: ReservationStatus }> {
    return this.http.post<{ id: number; status: ReservationStatus }>(
      `${BASE}/reservations/${id}/cancel`, null, { params: { code } });
  }

  widgetConfig(slug: string): Observable<WidgetConfig> {
    return this.http.get<WidgetConfig>(`${BASE}/widget/${slug}/config`);
  }

  // --- admin ------------------------------------------------------------------
  private admin(): { headers: HttpHeaders } {
    return { headers: new HttpHeaders({ 'X-Admin-Token': localStorage.getItem('buzz_admin_token') ?? '' }) };
  }

  adminVenues(): Observable<VenueSummary[]> {
    return this.http.get<VenueSummary[]>(`${BASE}/admin/venues`, this.admin());
  }

  adminTables(venueId: number): Observable<VenueTable[]> {
    return this.http.get<VenueTable[]>(`${BASE}/admin/venues/${venueId}/tables`, this.admin());
  }

  adminCreateTable(venueId: number, body: Partial<VenueTable>): Observable<VenueTable> {
    return this.http.post<VenueTable>(`${BASE}/admin/venues/${venueId}/tables`, body, this.admin());
  }

  adminUpdateTable(venueId: number, tableId: number, body: Partial<VenueTable>): Observable<VenueTable> {
    return this.http.put<VenueTable>(`${BASE}/admin/venues/${venueId}/tables/${tableId}`, body, this.admin());
  }

  adminDeleteTable(venueId: number, tableId: number): Observable<void> {
    return this.http.delete<void>(`${BASE}/admin/venues/${venueId}/tables/${tableId}`, this.admin());
  }

  adminSettings(venueId: number): Observable<BookingSettings> {
    return this.http.get<BookingSettings>(`${BASE}/admin/venues/${venueId}/booking-settings`, this.admin());
  }

  adminSaveSettings(venueId: number, body: BookingSettings): Observable<BookingSettings> {
    return this.http.put<BookingSettings>(`${BASE}/admin/venues/${venueId}/booking-settings`, body, this.admin());
  }

  adminHours(venueId: number): Observable<VenueHoursRow[]> {
    return this.http.get<VenueHoursRow[]>(`${BASE}/admin/venues/${venueId}/hours`, this.admin());
  }

  adminSaveHours(venueId: number, rows: VenueHoursRow[]): Observable<VenueHoursRow[]> {
    return this.http.put<VenueHoursRow[]>(`${BASE}/admin/venues/${venueId}/hours`,
      rows.map(({ weekday, open_time, close_time }) => ({ weekday, open_time, close_time })),
      this.admin());
  }

  adminOverrides(venueId: number): Observable<HoursOverride[]> {
    return this.http.get<HoursOverride[]>(`${BASE}/admin/venues/${venueId}/hours-override`, this.admin());
  }

  adminSaveOverrides(venueId: number, rows: HoursOverride[]): Observable<HoursOverride[]> {
    return this.http.put<HoursOverride[]>(`${BASE}/admin/venues/${venueId}/hours-override`,
      rows.map(({ date, is_closed, open_time, close_time }) => ({ date, is_closed, open_time, close_time })),
      this.admin());
  }

  adminReservations(venueId: number, date?: string, status?: string): Observable<Reservation[]> {
    const params: Record<string, string> = {};
    if (date) params['date'] = date;
    if (status) params['status'] = status;
    return this.http.get<Reservation[]>(`${BASE}/admin/venues/${venueId}/reservations`,
      { ...this.admin(), params });
  }

  adminConfirm(id: number, tableId?: number | null): Observable<Reservation> {
    return this.http.post<Reservation>(`${BASE}/admin/reservations/${id}/confirm`,
      { table_id: tableId ?? null }, this.admin());
  }

  adminDecline(id: number): Observable<Reservation> {
    return this.http.post<Reservation>(`${BASE}/admin/reservations/${id}/decline`, null, this.admin());
  }

  adminNoShow(id: number): Observable<Reservation> {
    return this.http.post<Reservation>(`${BASE}/admin/reservations/${id}/no-show`, null, this.admin());
  }

  adminWidgetConfig(venueId: number): Observable<WidgetConfigAdmin> {
    return this.http.get<WidgetConfigAdmin>(`${BASE}/admin/venues/${venueId}/widget-config`, this.admin());
  }

  adminSaveWidgetConfig(venueId: number, body: WidgetConfigAdmin): Observable<WidgetConfigAdmin> {
    return this.http.put<WidgetConfigAdmin>(`${BASE}/admin/venues/${venueId}/widget-config`, body, this.admin());
  }
}
