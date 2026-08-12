import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from '../core/api.service';
import {
  BookingSettings, HoursOverride, Reservation, VenueHoursRow, VenueSummary,
  VenueTable, WidgetConfigAdmin,
} from '../core/models';

type Tab = 'reservations' | 'tables' | 'hours' | 'settings' | 'widget';

const WEEKDAYS_RU = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];

const STATUS_RU: Record<string, string> = {
  pending: 'ожидает', confirmed: 'подтверждена', cancelled_by_guest: 'отменена гостем',
  cancelled_by_venue: 'отменена рестораном', no_show: 'no-show', completed: 'завершена',
};

function todayYmd(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

@Component({
  selector: 'buzz-admin-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-page.html',
  styleUrl: './admin-page.scss',
})
export class AdminPage implements OnInit {
  private api = inject(ApiService);

  readonly weekdays = WEEKDAYS_RU;
  readonly statusRu = STATUS_RU;

  // auth
  readonly authed = signal(!!localStorage.getItem('buzz_admin_token'));
  tokenInput = '';

  // venue + tab
  readonly venues = signal<VenueSummary[]>([]);
  readonly venueId = signal<number | null>(null);
  readonly tab = signal<Tab>('reservations');
  readonly toast = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  // reservations
  readonly reservations = signal<Reservation[]>([]);
  filterDate = todayYmd();
  filterStatus = '';
  readonly tablesById = signal<Record<number, VenueTable>>({});

  // tables
  readonly tables = signal<VenueTable[]>([]);
  newTable: Partial<VenueTable> = { name: '', capacity: 2, area: '', is_active: true, is_bookable: true };

  // hours
  readonly hours = signal<VenueHoursRow[]>([]);
  readonly overrides = signal<HoursOverride[]>([]);
  newOverride: HoursOverride = { date: todayYmd(), is_closed: true, open_time: null, close_time: null };

  // settings
  readonly settings = signal<BookingSettings | null>(null);

  // widget config
  readonly widgetCfg = signal<WidgetConfigAdmin | null>(null);

  ngOnInit(): void {
    if (this.authed()) this.loadVenues();
  }

  saveToken(): void {
    localStorage.setItem('buzz_admin_token', this.tokenInput.trim());
    this.authed.set(true);
    this.loadVenues();
  }

  logout(): void {
    localStorage.removeItem('buzz_admin_token');
    this.authed.set(false);
  }

  private fail(err: any): void {
    if (err?.status === 401) {
      this.logout();
      return;
    }
    this.error.set(err?.error?.detail?.message ?? 'Ошибка запроса');
    setTimeout(() => this.error.set(null), 4000);
  }

  private ok(msg: string): void {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(null), 2500);
  }

  loadVenues(): void {
    this.api.adminVenues().subscribe({
      next: vs => {
        this.venues.set(vs);
        if (vs.length && this.venueId() === null) {
          this.venueId.set(vs[0].id);
          this.loadTab();
        }
      },
      error: err => this.fail(err),
    });
  }

  pickVenue(id: number): void {
    this.venueId.set(id);
    this.loadTab();
  }

  setTab(t: Tab): void {
    this.tab.set(t);
    this.loadTab();
  }

  loadTab(): void {
    const v = this.venueId();
    if (v === null) return;
    switch (this.tab()) {
      case 'reservations': this.loadReservations(); break;
      case 'tables': this.loadTables(); break;
      case 'hours': this.loadHours(); break;
      case 'settings': this.loadSettings(); break;
      case 'widget': this.loadWidgetCfg(); break;
    }
  }

  // --- reservations -----------------------------------------------------------

  loadReservations(): void {
    const v = this.venueId()!;
    this.api.adminTables(v).subscribe({
      next: ts => this.tablesById.set(Object.fromEntries(ts.map(t => [t.id, t]))),
      error: () => {},
    });
    this.api.adminReservations(v, this.filterDate || undefined, this.filterStatus || undefined)
      .subscribe({ next: rs => this.reservations.set(rs), error: err => this.fail(err) });
  }

  resTime(r: Reservation): string {
    return new Date(r.starts_at + 'Z').toLocaleString('ru-RU', {
      timeZone: 'Europe/Riga', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  }

  tableLabel(r: Reservation): string {
    if (r.table_id == null) return '—';
    const t = this.tablesById()[r.table_id];
    return t ? `${t.name} (${t.capacity})` : `#${r.table_id}`;
  }

  confirmRes(r: Reservation): void {
    this.api.adminConfirm(r.id).subscribe({
      next: () => { this.ok(`Бронь ${r.confirmation_code} подтверждена`); this.loadReservations(); },
      error: err => this.fail(err),
    });
  }

  declineRes(r: Reservation): void {
    this.api.adminDecline(r.id).subscribe({
      next: () => { this.ok(`Бронь ${r.confirmation_code} отклонена`); this.loadReservations(); },
      error: err => this.fail(err),
    });
  }

  noShowRes(r: Reservation): void {
    this.api.adminNoShow(r.id).subscribe({
      next: () => { this.ok('Отмечено как no-show'); this.loadReservations(); },
      error: err => this.fail(err),
    });
  }

  // --- tables ------------------------------------------------------------------

  loadTables(): void {
    this.api.adminTables(this.venueId()!).subscribe({
      next: ts => this.tables.set(ts), error: err => this.fail(err),
    });
  }

  addTable(): void {
    if (!this.newTable.name || !this.newTable.capacity) return;
    this.api.adminCreateTable(this.venueId()!, {
      ...this.newTable,
      area: this.newTable.area || null,
    }).subscribe({
      next: () => {
        this.newTable = { name: '', capacity: 2, area: '', is_active: true, is_bookable: true };
        this.ok('Стол добавлен');
        this.loadTables();
      },
      error: err => this.fail(err),
    });
  }

  saveTable(t: VenueTable): void {
    this.api.adminUpdateTable(this.venueId()!, t.id, {
      name: t.name, capacity: t.capacity, area: t.area || null,
      is_active: t.is_active, is_bookable: t.is_bookable,
    }).subscribe({ next: () => this.ok('Сохранено'), error: err => this.fail(err) });
  }

  deleteTable(t: VenueTable): void {
    if (!confirm(`Удалить стол ${t.name}?`)) return;
    this.api.adminDeleteTable(this.venueId()!, t.id).subscribe({
      next: () => { this.ok('Стол удалён'); this.loadTables(); },
      error: err => this.fail(err),
    });
  }

  // --- hours ---------------------------------------------------------------------

  loadHours(): void {
    const v = this.venueId()!;
    this.api.adminHours(v).subscribe({ next: h => this.hours.set(h), error: err => this.fail(err) });
    this.api.adminOverrides(v).subscribe({ next: o => this.overrides.set(o), error: err => this.fail(err) });
  }

  hoursFor(weekday: number): VenueHoursRow[] {
    return this.hours().filter(h => h.weekday === weekday);
  }

  addInterval(weekday: number): void {
    this.hours.set([...this.hours(), { weekday, open_time: '12:00', close_time: '23:00' }]);
  }

  removeInterval(row: VenueHoursRow): void {
    this.hours.set(this.hours().filter(h => h !== row));
  }

  saveHours(): void {
    this.api.adminSaveHours(this.venueId()!, this.hours()).subscribe({
      next: rows => { this.hours.set(rows); this.ok('Часы сохранены'); },
      error: err => this.fail(err),
    });
  }

  addOverride(): void {
    if (!this.newOverride.date) return;
    const o = { ...this.newOverride };
    if (o.is_closed) { o.open_time = null; o.close_time = null; }
    this.overrides.set([...this.overrides(), o]);
    this.newOverride = { date: todayYmd(), is_closed: true, open_time: null, close_time: null };
    this.saveOverrides();
  }

  removeOverride(o: HoursOverride): void {
    this.overrides.set(this.overrides().filter(x => x !== o));
    this.saveOverrides();
  }

  saveOverrides(): void {
    this.api.adminSaveOverrides(this.venueId()!, this.overrides()).subscribe({
      next: rows => { this.overrides.set(rows); this.ok('Исключения сохранены'); },
      error: err => this.fail(err),
    });
  }

  // --- settings ---------------------------------------------------------------------

  loadSettings(): void {
    this.api.adminSettings(this.venueId()!).subscribe({
      next: s => this.settings.set(s), error: err => this.fail(err),
    });
  }

  saveSettings(): void {
    const s = this.settings();
    if (!s) return;
    this.api.adminSaveSettings(this.venueId()!, s).subscribe({
      next: saved => { this.settings.set(saved); this.ok('Настройки сохранены'); },
      error: err => this.fail(err),
    });
  }

  // --- widget config -------------------------------------------------------------------

  loadWidgetCfg(): void {
    this.api.adminWidgetConfig(this.venueId()!).subscribe({
      next: c => this.widgetCfg.set(c), error: err => this.fail(err),
    });
  }

  saveWidgetCfg(): void {
    const c = this.widgetCfg();
    if (!c) return;
    this.api.adminSaveWidgetConfig(this.venueId()!, c).subscribe({
      next: saved => { this.widgetCfg.set(saved); this.ok('Брендинг сохранён'); },
      error: err => this.fail(err),
    });
  }

  widgetUrl(): string {
    const c = this.widgetCfg();
    return c ? `${location.origin}/widget/${c.slug}` : '';
  }

  embedSnippet(): string {
    const url = this.widgetUrl();
    return `<iframe src="${url}" style="width:100%;min-height:720px;border:0;" loading="lazy"></iframe>`;
  }

  copyEmbed(): void {
    navigator.clipboard.writeText(this.embedSnippet()).then(() => this.ok('Сниппет скопирован'));
  }
}
