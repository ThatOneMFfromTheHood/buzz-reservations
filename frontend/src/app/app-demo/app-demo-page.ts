import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { ApiService } from '../core/api.service';
import { BookingConfig } from '../core/models';

/** Демо флоу 1 из ТЗ (§8): карточка заведения в приложении BUZZ →
 *  кнопка «Book a table» → white-label виджет во встроенном браузере. */
@Component({
  selector: 'buzz-app-demo',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './app-demo-page.html',
  styleUrl: './app-demo-page.scss',
})
export class AppDemoPage implements OnInit {
  private api = inject(ApiService);
  private sanitizer = inject(DomSanitizer);

  readonly booking = signal<BookingConfig | null>(null);
  readonly sheetOpen = signal(false);
  readonly activeTab = signal('Info');
  readonly slide = signal(0);

  readonly photos = ['/img/riviera-cover.webp', '/img/riviera-dish.webp', '/img/dessert.webp'];
  readonly tabs = [
    { name: 'Info', icon: 'ⓘ' },
    { name: 'Food', icon: '🍴' },
    { name: 'Drinks', icon: '🍷' },
    { name: 'Events', icon: '🎉' },
  ];
  readonly weekHours = [
    { d: 'Mon – Wed', h: '12:00 – 23:00' },
    { d: 'Thursday', h: '12:00 – 23:00' },
    { d: 'Friday', h: '12:00 – 23:00' },
    { d: 'Saturday', h: '12:00 – 23:00' },
    { d: 'Sunday', h: '12:00 – 23:00' },
  ];

  widgetUrl: SafeResourceUrl | null = null;

  ngOnInit(): void {
    document.title = 'BUZZ — In-app booking demo';
    this.api.bookingConfig(1).subscribe({
      next: b => this.booking.set(b),
      error: () => this.booking.set(null),
    });
    this.widgetUrl = this.sanitizer.bypassSecurityTrustResourceUrl('/widget/riviera');
  }

  now(): string {
    return new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  onCarouselScroll(el: HTMLElement): void {
    this.slide.set(Math.round(el.scrollLeft / el.clientWidth));
  }

  openSheet(): void {
    this.sheetOpen.set(true);
  }

  closeSheet(): void {
    this.sheetOpen.set(false);
  }
}
