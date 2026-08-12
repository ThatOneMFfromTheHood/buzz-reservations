export type ConfirmationMode = 'auto' | 'manual';
export type ReservationStatus =
  | 'pending' | 'confirmed' | 'cancelled_by_guest'
  | 'cancelled_by_venue' | 'no_show' | 'completed';
export type Lang = 'en' | 'ru' | 'lv';

export interface BookingConfig {
  venue_id: number;
  venue_name: string;
  address: string;
  booking_enabled: boolean;
  confirmation_mode: ConfirmationMode;
  min_party_size: number;
  max_party_size: number;
  slot_step_min: number;
  booking_duration_min: number;
  advance_booking_days: number;
  cancellation_hours: number;
  phone: string;
  timezone: string;
}

export interface Slot {
  time: string;
  starts_at: string;
  free_tables: number;
}

export interface Availability {
  date: string;
  party_size: number;
  slots: Slot[];
}

export interface InfoItem {
  icon: string;
  title: string;
  text: string;
}

export interface WidgetConfig {
  slug: string;
  venue_id: number;
  venue_name: string;
  address: string;
  primary_color: string;
  text_color: string;
  bg_color: string;
  form_control_color: string;
  font: string;
  corner_style: 'rounded' | 'square';
  text_alignment: string;
  default_lang: Lang;
  logo_url: string | null;
  policy_text: string;
  info_items: InfoItem[];
  booking: BookingConfig;
}

export interface Reservation {
  id: number;
  venue_id: number;
  status: ReservationStatus;
  confirmation_code: string;
  party_size: number;
  starts_at: string;
  ends_at: string;
  guest_name: string;
  guest_phone: string;
  guest_email: string;
  special_request: string | null;
  source: 'app' | 'widget' | 'admin';
  table_id: number | null;
  created_at: string;
}

export interface VenueTable {
  id: number;
  venue_id: number;
  name: string;
  capacity: number;
  area: string | null;
  is_active: boolean;
  is_bookable: boolean;
}

export interface BookingSettings {
  booking_enabled: boolean;
  confirmation_mode: ConfirmationMode;
  booking_duration_min: number;
  slot_step_min: number;
  max_party_size: number;
  min_party_size: number;
  advance_booking_days: number;
  min_lead_time_min: number;
  hold_pending_min: number;
  phone: string;
  cancellation_hours: number;
}

export interface VenueHoursRow {
  id?: number;
  weekday: number;
  open_time: string;
  close_time: string;
}

export interface HoursOverride {
  id?: number;
  date: string;
  is_closed: boolean;
  open_time: string | null;
  close_time: string | null;
}

export interface WidgetConfigAdmin {
  slug: string;
  primary_color: string;
  text_color: string;
  bg_color: string;
  form_control_color: string;
  font: string;
  corner_style: 'rounded' | 'square';
  text_alignment: string;
  default_lang: Lang;
  logo_url: string | null;
  policy_text: string;
  info_items: InfoItem[];
}

export interface VenueSummary {
  id: number;
  name: string;
  address: string;
}

export interface ApiError {
  code: string;
  message: string;
}
