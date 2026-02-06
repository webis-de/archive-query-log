import { Injectable, signal, inject } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';

export interface Language {
  code: string;
  name: string;
  flag: string;
}

@Injectable({
  providedIn: 'root',
})
export class LanguageService {
  readonly availableLanguages: Language[] = [
    { code: 'en', name: 'English', flag: '🇬🇧' },
    { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
    { code: 'fr', name: 'Français', flag: '🇫🇷' },
  ];
  currentLanguage = signal<Language>(this.availableLanguages[0]);

  private readonly STORAGE_KEY = 'app_language';
  private readonly translate = inject(TranslateService);

  constructor() {
    this.translate.addLangs(this.availableLanguages.map(l => l.code));
  }

  initLanguage(): void {
    const savedLang = localStorage.getItem(this.STORAGE_KEY);
    const langCode = savedLang || this.translate.getBrowserLang() || 'en';
    const language = this.availableLanguages.find(l => l.code === langCode);

    if (language) {
      this.currentLanguage.set(language);
    }
  }

  setLanguage(langCode: string): void {
    const language = this.availableLanguages.find(l => l.code === langCode);

    if (language) {
      this.translate.use(langCode);
      this.currentLanguage.set(language);
      localStorage.setItem(this.STORAGE_KEY, langCode);
    }
  }

  getCurrentLanguageCode(): string {
    return this.currentLanguage().code;
  }

  toggleLanguage(): void {
    const currentIndex = this.availableLanguages.findIndex(
      l => l.code === this.currentLanguage().code,
    );
    const nextIndex = (currentIndex + 1) % this.availableLanguages.length;
    this.setLanguage(this.availableLanguages[nextIndex].code);
  }

  formatDate(dateString: string): string {
    const locale = this.getCurrentLanguageCode();
    const d = this.parseDate(dateString);
    if (!d) return dateString; // fallback to original string if we cannot parse

    // Only show day, month and year (no clock time)
    return d.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  }

  formatDateTime(dateString: string): string {
    const locale = this.getCurrentLanguageCode();
    const d = this.parseDate(dateString);
    if (!d) return dateString;

    return d.toLocaleString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  /**
   * Formats a Date object to ISO date string (YYYY-MM-DD)
   */
  formatDateForInput(date: Date): string {
    return date.toISOString().split('T')[0];
  }

  private parseDate(dateString: string): Date | null {
    if (!dateString) return null;

    // If already a Date object string (ISO) or numeric timestamp
    // try standard parse first
    const asNumber = Number(dateString);
    if (!Number.isNaN(asNumber) && isFinite(asNumber)) {
      const d = new Date(asNumber);
      if (!isNaN(d.getTime())) return d;
    }

    // ISO-like (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
    if (/^\d{4}-\d{2}-\d{2}/.test(dateString)) {
      const d = new Date(dateString);
      if (!isNaN(d.getTime())) return d;
    }

    // Common German date format: DD.MM.YYYY or DD.MM.YYYY HH:MM
    const germanMatch = dateString.match(
      /^(\d{1,2})\.(\d{1,2})\.(\d{4})(?:[ T](\d{1,2}):(\d{2}))?/,
    );
    if (germanMatch) {
      const day = parseInt(germanMatch[1], 10);
      const month = parseInt(germanMatch[2], 10) - 1;
      const year = parseInt(germanMatch[3], 10);
      const hour = germanMatch[4] ? parseInt(germanMatch[4], 10) : 0;
      const minute = germanMatch[5] ? parseInt(germanMatch[5], 10) : 0;
      const d = new Date(Date.UTC(year, month, day, hour, minute, 0));
      if (!isNaN(d.getTime())) return d;
    }

    // Fallback: try Date.parse once more
    const parsed = Date.parse(dateString);
    if (!Number.isNaN(parsed)) {
      const d = new Date(parsed);
      if (!isNaN(d.getTime())) return d;
    }

    return null;
  }
}
