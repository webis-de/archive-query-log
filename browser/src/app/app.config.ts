import {
  ApplicationConfig,
  provideZoneChangeDetection,
  importProvidersFrom,
  provideAppInitializer,
  inject,
} from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { TranslateModule, MissingTranslationHandler, TranslateService } from '@ngx-translate/core';
import { provideTranslateHttpLoader } from '@ngx-translate/http-loader';

import { routes } from './app.routes';
import { headerInterceptor } from './interceptors/header.interceptor';
import { CustomMissingTranslationHandler } from './config/translation.config';
import { LanguageService } from './services/language.service';

// Initialize language service before app starts
const initializeLanguage = () => {
  const languageService = inject(LanguageService);
  const translateService = inject(TranslateService);
  const savedLang = localStorage.getItem('app_language');
  const langCode = savedLang || translateService.getBrowserLang() || 'en';

  // Pre-load the language to ensure translations are available
  translateService.use(langCode);
  languageService.initLanguage();
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([headerInterceptor])),
    importProvidersFrom(
      TranslateModule.forRoot({
        fallbackLang: 'en',
        missingTranslationHandler: {
          provide: MissingTranslationHandler,
          useClass: CustomMissingTranslationHandler,
        },
      }),
    ),
    provideTranslateHttpLoader({
      prefix: './assets/i18n/',
      suffix: '.json',
    }),
    provideAppInitializer(initializeLanguage),
  ],
};
