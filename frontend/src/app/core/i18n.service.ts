import { Injectable, signal } from '@angular/core';
import { Lang } from './models';

const STRINGS: Record<string, Record<Lang, string>> = {
  book_a_table:      { en: 'Book a table', ru: 'Забронировать стол', lv: 'Rezervēt galdiņu' },
  guests:            { en: 'guests', ru: 'гостей', lv: 'viesi' },
  guest_one:         { en: 'guest', ru: 'гость', lv: 'viesis' },
  select_time:       { en: 'Select time:', ru: 'Время:', lv: 'Pieejamie laiki' },
  show_more:         { en: 'Show more', ru: 'Показать больше', lv: 'Rādīt vairāk' },
  show_less:         { en: 'Show less', ru: 'Свернуть', lv: 'Rādīt mazāk' },
  continue_:         { en: 'Continue', ru: 'Далее', lv: 'Turpināt' },
  back:              { en: 'Back', ru: 'Назад', lv: 'Atpakaļ' },
  your_details:      { en: 'Your details', ru: 'Ваши данные', lv: 'Jūsu dati' },
  name:              { en: 'Name', ru: 'Имя', lv: 'Vārds' },
  phone:             { en: 'Phone', ru: 'Телефон', lv: 'Tālrunis' },
  email:             { en: 'Email', ru: 'Email', lv: 'E-pasts' },
  special_request:   { en: 'Special request (optional)', ru: 'Пожелания (необязательно)', lv: 'Īpašas vēlmes (nav obligāti)' },
  confirm_booking:   { en: 'Confirm booking', ru: 'Подтвердить бронь', lv: 'Apstiprināt rezervāciju' },
  booking_policy:    { en: 'Booking policy', ru: 'Правила бронирования', lv: 'Rezervācijas noteikumi' },
  information:       { en: 'Information', ru: 'Информация', lv: 'Informācija' },
  confirmed_title:   { en: 'Booking confirmed!', ru: 'Бронь подтверждена!', lv: 'Rezervācija apstiprināta!' },
  pending_title:     { en: 'Request sent', ru: 'Заявка отправлена', lv: 'Pieprasījums nosūtīts' },
  pending_note:      { en: 'We are waiting for the restaurant to confirm your booking. You will get a notification.',
                       ru: 'Ждём подтверждения ресторана. Вы получите уведомление.',
                       lv: 'Gaidām restorāna apstiprinājumu. Jūs saņemsiet paziņojumu.' },
  your_code:         { en: 'Your booking code', ru: 'Код вашей брони', lv: 'Jūsu rezervācijas kods' },
  cancel_booking:    { en: 'Cancel reservation', ru: 'Отменить бронь', lv: 'Atcelt rezervāciju' },
  cancelled_title:   { en: 'Reservation cancelled', ru: 'Бронь отменена', lv: 'Rezervācija atcelta' },
  new_booking:       { en: 'Make another booking', ru: 'Новая бронь', lv: 'Jauna rezervācija' },
  call_us_large:     { en: 'For larger groups, please contact us:', ru: 'Если вы планируете бронирование для большего числа человек, свяжитесь с нами:', lv: 'Lielākām grupām, lūdzu, sazinieties ar mums:' },
  slot_taken:        { en: 'This time was just taken — please pick another slot.', ru: 'Это время только что заняли — выберите другое.', lv: 'Šis laiks tikko tika aizņemts — izvēlieties citu.' },
  no_slots:          { en: 'No available times on this date', ru: 'На эту дату нет доступного времени', lv: 'Šajā datumā nav pieejamu laiku' },
  pick_date:         { en: 'Select a date to see available times', ru: 'Выберите дату, чтобы увидеть доступные времена', lv: 'Izvēlieties datumu, lai redzētu pieejamos laikus' },
  date_label:        { en: 'Booking date', ru: 'Дата бронирования', lv: 'Rezervācijas datums' },
  partnered:         { en: 'Partnered with', ru: 'Партнёр сервиса', lv: 'Sadarbībā ar' },
  error_generic:     { en: 'Something went wrong. Please try again.', ru: 'Что-то пошло не так. Попробуйте ещё раз.', lv: 'Kaut kas nogāja greizi. Lūdzu, mēģiniet vēlreiz.' },
  loading:           { en: 'Loading…', ru: 'Загрузка…', lv: 'Ielādē…' },
  booking_for:       { en: 'Booking for', ru: 'Бронь на', lv: 'Rezervācija' },
  at:                { en: 'at', ru: 'в', lv: 'plkst.' },
  contact_required:  { en: 'Please leave a phone or email', ru: 'Укажите телефон или email', lv: 'Norādiet tālruni vai e-pastu' },
  status_pending:    { en: 'Waiting for confirmation', ru: 'Ожидает подтверждения', lv: 'Gaida apstiprinājumu' },
  status_confirmed:  { en: 'Confirmed', ru: 'Подтверждена', lv: 'Apstiprināta' },
  status_cancelled:  { en: 'Cancelled', ru: 'Отменена', lv: 'Atcelta' },
};

@Injectable({ providedIn: 'root' })
export class I18nService {
  readonly lang = signal<Lang>('en');

  readonly locales: Record<Lang, string> = { en: 'en-GB', ru: 'ru-RU', lv: 'lv-LV' };

  t(key: string): string {
    const row = STRINGS[key];
    return row ? row[this.lang()] : key;
  }

  locale(): string {
    return this.locales[this.lang()];
  }

  monthLabel(d: Date): string {
    return d.toLocaleDateString(this.locale(), { month: 'long', year: 'numeric' });
  }

  weekdayShort(d: Date): string {
    const s = d.toLocaleDateString(this.locale(), { weekday: 'short' });
    return s.replace('.', '');
  }

  longDate(d: Date): string {
    return d.toLocaleDateString(this.locale(), { weekday: 'long', day: 'numeric', month: 'long' });
  }
}
