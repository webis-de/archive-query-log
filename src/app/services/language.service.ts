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
  private readonly STORAGE_KEY = 'app_language';
  private readonly translate = inject(TranslateService);

  // Available languages
  readonly availableLanguages: Language[] = [
    { code: 'en', name: 'English', flag: '🇬🇧' },
    { code: 'de', name: 'Deutsch', flag: '🇩🇪' },
    { code: 'fr', name: 'Français', flag: '🇫🇷' },
  ];

  // Current language signal
  currentLanguage = signal<Language>(this.availableLanguages[0]);

  constructor() {
    this.initLanguage();
  }

  /**
   * Initialize language from localStorage or browser settings
   */
  private initLanguage(): void {
    // Try to get saved language from localStorage
    const savedLang = localStorage.getItem(this.STORAGE_KEY);

    let langCode: string;

    if (savedLang) {
      langCode = savedLang;
    } else {
      // Get browser language
      const browserLang = this.translate.getBrowserLang() || 'en';
      langCode = this.availableLanguages.some(l => l.code === browserLang) ? browserLang : 'en';
    }

    this.setLanguage(langCode);
  }

  /**
   * Set the application language
   */
  setLanguage(langCode: string): void {
    const language = this.availableLanguages.find(l => l.code === langCode);

    if (language) {
      this.translate.use(langCode);
      this.currentLanguage.set(language);
      localStorage.setItem(this.STORAGE_KEY, langCode);
    }
  }

  /**
   * Get the current language code
   */
  getCurrentLanguageCode(): string {
    return this.currentLanguage().code;
  }

  /**
   * Toggle between available languages
   */
  toggleLanguage(): void {
    const currentIndex = this.availableLanguages.findIndex(
      l => l.code === this.currentLanguage().code,
    );
    const nextIndex = (currentIndex + 1) % this.availableLanguages.length;
    this.setLanguage(this.availableLanguages[nextIndex].code);
  }
}
