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
    return new Date(dateString).toLocaleString(locale, {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
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
}
