import { TestBed } from '@angular/core/testing';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { LanguageService } from './language.service';

describe('LanguageService', () => {
  let service: LanguageService;

  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();

    TestBed.configureTestingModule({
      imports: [TranslateModule.forRoot()],
      providers: [LanguageService, TranslateService],
    });
    
    const translate = TestBed.inject(TranslateService);
    spyOn(translate, 'getBrowserLang').and.returnValue('en');

    service = TestBed.inject(LanguageService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should initialize with default language', () => {
    expect(service.currentLanguage().code).toBe('en');
  });

  it('should change language', () => {
    service.setLanguage('de');
    expect(service.currentLanguage().code).toBe('de');
  });

  it('should toggle between languages', () => {
    const initialLang = service.currentLanguage().code;
    service.toggleLanguage();
    expect(service.currentLanguage().code).not.toBe(initialLang);
  });
});
