import { CommonModule } from '@angular/common';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Lang, Reservation, Slot, WidgetConfig } from '../core/models';

type Step = 'slot' | 'details' | 'success' | 'cancelled';

function ymd(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

@Component({
  selector: 'buzz-widget-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './widget-page.html',
  styleUrl: './widget-page.scss',
})
export class WidgetPage implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  readonly i18n = inject(I18nService);

  readonly cfg = signal<WidgetConfig | null>(null);
  readonly loadError = signal(false);
  readonly buzzLogoOk = signal(true);

  readonly step = signal<Step>('slot');

  // --- step 1 state ---
  readonly weekStart = signal<Date>(new Date());     // first visible day of week strip
  readonly selectedDate = signal<Date | null>(null);
  readonly partySize = signal(2);
  readonly slots = signal<Slot[] | null>(null);      // null = not loaded yet
  readonly slotsLoading = signal(false);
  readonly selectedSlot = signal<Slot | null>(null);
  readonly showAllSlots = signal(false);
  readonly policyExpanded = signal(false);

  // --- step 2 state ---
  guestName = '';
  guestPhone = '';
  guestEmail = '';
  specialRequest = '';
  readonly submitting = signal(false);
  readonly formError = signal<string | null>(null);

  // --- result ---
  readonly reservation = signal<Reservation | null>(null);
  readonly cancelling = signal(false);
  private idempotencyKey = crypto.randomUUID();

  readonly today = new Date();

  readonly weekDays = computed<Date[]>(() => {
    const start = this.weekStart();
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(start);
      d.setDate(d.getDate() + i);
      return d;
    });
  });

  readonly partyOptions = computed<number[]>(() => {
    const b = this.cfg()?.booking;
    if (!b) return [1, 2, 3, 4];
    const opts: number[] = [];
    for (let n = b.min_party_size; n <= b.max_party_size; n++) opts.push(n);
    return opts;
  });

  readonly visibleSlots = computed<Slot[]>(() => {
    const all = this.slots() ?? [];
    return this.showAllSlots() ? all : all.slice(0, 4);
  });

  readonly maxDate = computed<Date>(() => {
    const b = this.cfg()?.booking;
    const d = new Date();
    d.setDate(d.getDate() + (b?.advance_booking_days ?? 60));
    return d;
  });

  ngOnInit(): void {
    const slug = this.route.snapshot.paramMap.get('slug')!;
    // week strip starts on Monday of the current week
    const start = new Date();
    start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    this.weekStart.set(start);

    this.api.widgetConfig(slug).subscribe({
      next: cfg => {
        this.cfg.set(cfg);
        this.applyBranding(cfg);
        this.partySize.set(Math.min(Math.max(2, cfg.booking.min_party_size), cfg.booking.max_party_size));
      },
      error: () => this.loadError.set(true),
    });
  }

  /** Branding: stored config first, query params override for previews (ТЗ 5.6). */
  private applyBranding(cfg: WidgetConfig): void {
    const q = this.route.snapshot.queryParamMap;
    const pick = (param: string, stored: string) => {
      const v = q.get(param);
      return v ? (v.startsWith('#') || /^[0-9a-fA-F]{6}$/.test(v) === false ? v : `#${v}`) : stored;
    };
    const primary = pick('primaryColor', cfg.primary_color);
    const text = pick('textColor', cfg.text_color);
    const bg = pick('bgColor', cfg.bg_color);
    const formControl = pick('formControlBgColor', cfg.form_control_color);
    const font = q.get('googleFont') ?? cfg.font;
    const corner = (q.get('cornerStyle') ?? cfg.corner_style) as 'rounded' | 'square';
    const lang = (q.get('lang') ?? cfg.default_lang) as Lang;

    this.i18n.lang.set(['en', 'ru', 'lv'].includes(lang) ? lang : 'en');

    const root = document.documentElement;
    root.style.setProperty('--w-primary', primary);
    root.style.setProperty('--w-text', text);
    root.style.setProperty('--w-bg', bg);
    root.style.setProperty('--w-form', formControl);
    root.style.setProperty('--w-radius', corner === 'square' ? '2px' : '12px');

    // 'system' / 'Inter' / пусто = системный стек BUZZ, иначе Google Font
    if (!font || ['system', 'System', 'Inter'].includes(font)) {
      root.style.setProperty('--w-font', 'var(--buzz-font)');
    } else {
      root.style.setProperty('--w-font', `'${font}', var(--buzz-font)`);
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = `https://fonts.googleapis.com/css2?family=${encodeURIComponent(font)}:wght@400;500;600;700&display=swap`;
      document.head.appendChild(link);
    }
    document.title = `${cfg.venue_name} — Book a table`;
  }

  setLang(l: Lang): void {
    this.i18n.lang.set(l);
  }

  // --- calendar ----------------------------------------------------------------

  prevWeek(): void {
    const d = new Date(this.weekStart());
    d.setDate(d.getDate() - 7);
    this.weekStart.set(d);
  }

  nextWeek(): void {
    const d = new Date(this.weekStart());
    d.setDate(d.getDate() + 7);
    this.weekStart.set(d);
  }

  canGoPrev(): boolean {
    const first = this.weekDays()[0];
    return first > this.today;
  }

  isPast(d: Date): boolean {
    const t = new Date(this.today);
    t.setHours(0, 0, 0, 0);
    return d < t;
  }

  isTooFar(d: Date): boolean {
    return d > this.maxDate();
  }

  isSelected(d: Date): boolean {
    const s = this.selectedDate();
    return !!s && ymd(s) === ymd(d);
  }

  selectDate(d: Date): void {
    if (this.isPast(d) || this.isTooFar(d)) return;
    this.selectedDate.set(d);
    this.selectedSlot.set(null);
    this.showAllSlots.set(false);
    this.loadSlots();
  }

  onPartyChange(): void {
    this.selectedSlot.set(null);
    if (this.selectedDate()) this.loadSlots();
  }

  private loadSlots(): void {
    const cfg = this.cfg();
    const date = this.selectedDate();
    if (!cfg || !date) return;
    this.slotsLoading.set(true);
    this.api.availability(cfg.venue_id, ymd(date), this.partySize()).subscribe({
      next: a => {
        this.slots.set(a.slots);
        this.slotsLoading.set(false);
      },
      error: () => {
        this.slots.set([]);
        this.slotsLoading.set(false);
      },
    });
  }

  pickSlot(s: Slot): void {
    this.selectedSlot.set(s);
  }

  goToDetails(): void {
    if (this.selectedSlot()) {
      this.formError.set(null);
      this.step.set('details');
    }
  }

  // --- step 2 -------------------------------------------------------------------

  submit(): void {
    const cfg = this.cfg();
    const slot = this.selectedSlot();
    if (!cfg || !slot || this.submitting()) return;
    if (!this.guestName.trim()) {
      this.formError.set(this.i18n.t('name'));
      return;
    }
    if (!this.guestPhone.trim() && !this.guestEmail.trim()) {
      this.formError.set(this.i18n.t('contact_required'));
      return;
    }
    this.submitting.set(true);
    this.formError.set(null);
    this.api.createReservation(cfg.venue_id, {
      party_size: this.partySize(),
      starts_at: slot.starts_at,
      guest_name: this.guestName.trim(),
      guest_phone: this.guestPhone.trim(),
      guest_email: this.guestEmail.trim(),
      special_request: this.specialRequest.trim() || null,
      source: 'widget',
      lang: this.i18n.lang(),
    }, this.idempotencyKey).subscribe({
      next: res => {
        this.reservation.set(res);
        this.submitting.set(false);
        this.step.set('success');
      },
      error: err => {
        this.submitting.set(false);
        if (err?.status === 409) {
          this.formError.set(this.i18n.t('slot_taken'));
          this.step.set('slot');
          this.selectedSlot.set(null);
          this.idempotencyKey = crypto.randomUUID();
          this.loadSlots();
        } else {
          this.formError.set(err?.error?.detail?.message ?? this.i18n.t('error_generic'));
        }
      },
    });
  }

  cancelReservation(): void {
    const res = this.reservation();
    if (!res || this.cancelling()) return;
    this.cancelling.set(true);
    this.api.cancelReservation(res.id, res.confirmation_code).subscribe({
      next: () => {
        this.cancelling.set(false);
        this.step.set('cancelled');
      },
      error: err => {
        this.cancelling.set(false);
        this.formError.set(err?.error?.detail?.message ?? this.i18n.t('error_generic'));
      },
    });
  }

  startOver(): void {
    this.reservation.set(null);
    this.selectedSlot.set(null);
    this.selectedDate.set(null);
    this.slots.set(null);
    this.guestName = this.guestPhone = this.guestEmail = this.specialRequest = '';
    this.idempotencyKey = crypto.randomUUID();
    this.formError.set(null);
    this.step.set('slot');
  }

  // --- template helpers -----------------------------------------------------------

  slotDateLabel(): string {
    const d = this.selectedDate();
    return d ? this.i18n.longDate(d) : '';
  }

  reservationDateLabel(): string {
    const res = this.reservation();
    if (!res) return '';
    const d = new Date(res.starts_at + 'Z');
    return d.toLocaleString(this.i18n.locale(), {
      timeZone: this.cfg()?.booking.timezone ?? 'Europe/Riga',
      weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
    });
  }

  policyParagraphs(): string[] {
    const t = this.cfg()?.policy_text ?? '';
    return t.split(/\n\n+/).filter(p => p.trim());
  }

  infoIcon(icon: string): string {
    const map: Record<string, string> = {
      clock: '🕐', child: '🧒', dress: '👔', pets: '🐾', lock: '🔒',
      wheelchair: '♿', group: '👥', cancel: '↩️', bill: '💳', kitchen: '🍽️',
    };
    return map[icon] ?? 'ℹ️';
  }
}
