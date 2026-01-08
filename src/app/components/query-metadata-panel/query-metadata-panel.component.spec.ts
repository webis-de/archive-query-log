import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppQueryMetadataPanelComponent } from './query-metadata-panel.component';
import { provideHttpClient } from '@angular/common/http';
import { SearchResult } from '../../models/search.model';
import { SessionService } from '../../services/session.service';
import { signal, WritableSignal } from '@angular/core';
import { TranslateModule } from '@ngx-translate/core';

describe('AppQueryMetadataPanelComponent', () => {
  let component: AppQueryMetadataPanelComponent;
  let fixture: ComponentFixture<AppQueryMetadataPanelComponent>;
  let mockSessionService: { sidebarCollapsed: WritableSignal<boolean> };

  const mockSearchResult: SearchResult = {
    _id: 'test-123',
    _score: 0.95,
    _source: {
      url_query: 'Test Query',
      capture: {
        url: 'https://example.com/test',
        timestamp: '2025-01-01T12:00:00Z',
        mimetype: 'text/html',
      },
      provider: {
        domain: 'example.com',
      },
      archive: {
        memento_api_url: 'https://web.archive.org/web',
      },
    },
  } as SearchResult;

  const mockSearchResultWithoutArchive: SearchResult = {
    _id: 'test-456',
    _score: 0.85,
    _source: {
      url_query: 'Test Query 2',
      capture: {
        url: 'https://example.com/test2',
        timestamp: '2024-06-15T08:30:45Z',
        mimetype: 'text/html',
      },
      provider: {
        domain: 'example.com',
      },
    },
  } as SearchResult;

  beforeEach(async () => {
    mockSessionService = {
      sidebarCollapsed: signal(true),
    };

    await TestBed.configureTestingModule({
      imports: [AppQueryMetadataPanelComponent, TranslateModule.forRoot()],
      providers: [provideHttpClient(), { provide: SessionService, useValue: mockSessionService }],
    }).compileComponents();

    fixture = TestBed.createComponent(AppQueryMetadataPanelComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('isOpen', false);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should apply correct classes when sidebar is collapsed', () => {
    mockSessionService.sidebarCollapsed.set(true);
    fixture.componentRef.setInput('isOpen', true);
    fixture.detectChanges();

    const classes = component.panelClasses();
    expect(classes).toContain('w-[60vw]');
    expect(classes).toContain('transition-[width]');
  });

  it('should apply correct classes when sidebar is expanded', () => {
    mockSessionService.sidebarCollapsed.set(false);
    fixture.componentRef.setInput('isOpen', true);
    fixture.detectChanges();

    const classes = component.panelClasses();
    expect(classes).toContain('w-[calc(60vw-20rem)]');
  });

  it('should emit closePanel event when close button is clicked', () => {
    fixture.componentRef.setInput('isOpen', true);
    fixture.detectChanges();

    let closeCalled = false;
    component.closePanel.subscribe(() => {
      closeCalled = true;
    });

    component.onClose();
    expect(closeCalled).toBe(true);
  });

  it('should change active tab when onTabChange is called', () => {
    component.onTabChange('html');
    expect(component.activeTab()).toBe('html');

    component.onTabChange('metadata');
    expect(component.activeTab()).toBe('metadata');
  });

  it('should render search result data when provided', () => {
    fixture.componentRef.setInput('searchResult', mockSearchResult);
    fixture.componentRef.setInput('isOpen', true);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test Query');
    expect(compiled.textContent).toContain('https://example.com/test');
  });

  it('should have correct default active tab', () => {
    expect(component.activeTab()).toBe('text');
  });

  // -------------------- Memento URL Tests --------------------
  describe('formatTimestampForMemento', () => {
    it('should format ISO timestamp correctly', () => {
      const result = component.formatTimestampForMemento('2025-01-01T12:00:00Z');
      expect(result).toBe('20250101120000');
    });

    it('should handle timestamps with timezone offsets', () => {
      const result = component.formatTimestampForMemento('2024-06-15T08:30:45+00:00');
      expect(result).toBe('20240615083045');
    });

    it('should handle timestamps without timezone', () => {
      const result = component.formatTimestampForMemento('2023-12-25T18:45:30');
      // Result depends on local timezone, so we just verify it's a valid format
      expect(result).toMatch(/^\d{14}$/);
    });

    it('should return empty string for invalid timestamp', () => {
      const result = component.formatTimestampForMemento('invalid-date');
      expect(result).toBe('');
    });

    it('should return empty string for empty input', () => {
      const result = component.formatTimestampForMemento('');
      expect(result).toBe('');
    });

    it('should pad single-digit values correctly', () => {
      const result = component.formatTimestampForMemento('2025-01-05T03:07:09Z');
      expect(result).toBe('20250105030709');
    });
  });

  describe('mementoUrlString computed signal', () => {
    it('should return empty string when no search result', () => {
      fixture.componentRef.setInput('searchResult', null);
      fixture.detectChanges();
      expect(component.mementoUrlString()).toBe('');
    });

    it('should construct correct memento URL string from search result', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.detectChanges();
      const url = component.mementoUrlString();
      expect(url).toBe('https://web.archive.org/web/20250101120000/https://example.com/test');
    });

    it('should return capture URL when archive data is missing', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResultWithoutArchive);
      fixture.detectChanges();
      const url = component.mementoUrlString();
      expect(url).toBe('https://example.com/test2');
    });
  });

  describe('mementoUrl computed signal', () => {
    it('should return null when no search result', () => {
      fixture.componentRef.setInput('searchResult', null);
      fixture.detectChanges();
      expect(component.mementoUrl()).toBeNull();
    });

    it('should construct correct memento URL from search result', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.detectChanges();
      const url = component.mementoUrl();
      expect(url).toBeTruthy();
    });

    it('should handle missing archive data gracefully', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResultWithoutArchive);
      fixture.detectChanges();
      const url = component.mementoUrl();
      expect(url).toBeTruthy();
    });

    it('should use memento_api_url as base', () => {
      const result = mockSearchResult;
      const mementoApiUrl = result._source.archive?.memento_api_url;
      const timestamp = result._source.capture.timestamp;

      expect(mementoApiUrl).toBe('https://web.archive.org/web');
      expect(component.formatTimestampForMemento(timestamp)).toBe('20250101120000');
    });
  });

  describe('archiveDate computed signal', () => {
    it('should return empty string when no search result', () => {
      fixture.componentRef.setInput('searchResult', null);
      fixture.detectChanges();
      expect(component.archiveDate()).toBe('');
    });

    it('should format archive date for display', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.detectChanges();
      const result = component.archiveDate();
      expect(result).toContain('2025');
      expect(result).toContain('January');
      expect(result).toContain('1');
    });

    it('should return empty string for invalid timestamp', () => {
      const invalidResult = {
        ...mockSearchResult,
        _source: {
          ...mockSearchResult._source,
          capture: {
            ...mockSearchResult._source.capture,
            timestamp: 'invalid-date',
          },
        },
      } as SearchResult;
      fixture.componentRef.setInput('searchResult', invalidResult);
      fixture.detectChanges();
      expect(component.archiveDate()).toBe('');
    });

    it('should return empty string for empty timestamp', () => {
      const emptyResult = {
        ...mockSearchResult,
        _source: {
          ...mockSearchResult._source,
          capture: {
            ...mockSearchResult._source.capture,
            timestamp: '',
          },
        },
      } as SearchResult;
      fixture.componentRef.setInput('searchResult', emptyResult);
      fixture.detectChanges();
      expect(component.archiveDate()).toBe('');
    });
  });

  describe('Website tab with archived snapshot', () => {
    it('should display archive date info when website tab is active', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');
      fixture.detectChanges();

      const compiled = fixture.nativeElement as HTMLElement;
      expect(compiled.textContent).toContain('metadata.websitePreview');
      expect(compiled.textContent).toContain('metadata.website.snapshotDate');
    });

    it('should display archive URL in website tab', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');
      fixture.detectChanges();

      const compiled = fixture.nativeElement as HTMLElement;
      expect(compiled.textContent).toContain('web.archive.org');
    });

    it('should have iframe with archived snapshot', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');
      fixture.detectChanges();

      const iframe = fixture.nativeElement.querySelector('iframe');
      expect(iframe).toBeTruthy();
      // The title attribute now uses translation key with interpolation
      expect(iframe.getAttribute('title')).toContain('metadata.website.iframeTitle');
    });

    it('should show loading state when switching to website tab', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');

      expect(component.isIframeLoading()).toBe(true);
      expect(component.iframeError()).toBe(false);
    });

    it('should display loading spinner when iframe is loading', () => {
      // Prevent iframe load event from resetting loading state
      spyOn(component, 'onIframeLoad');

      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');
      fixture.detectChanges();

      const compiled = fixture.nativeElement as HTMLElement;
      expect(compiled.textContent).toContain('metadata.website.loadingSnapshot');
      expect(compiled.querySelector('.loading-spinner')).toBeTruthy();
    });

    it('should clear loading state when iframe loads successfully', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.isIframeLoading.set(true);

      component.onIframeLoad();

      expect(component.isIframeLoading()).toBe(false);
      expect(component.iframeError()).toBe(false);
    });

    it('should set error state when iframe fails to load', () => {
      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.isIframeLoading.set(true);

      component.onIframeError();

      expect(component.isIframeLoading()).toBe(false);
      expect(component.iframeError()).toBe(true);
    });

    it('should display error message when iframe fails to load', () => {
      // Prevent iframe load event from interfering
      spyOn(component, 'onIframeLoad');

      fixture.componentRef.setInput('searchResult', mockSearchResult);
      fixture.componentRef.setInput('isOpen', true);
      component.onTabChange('website');
      fixture.detectChanges(); // Trigger effect first to set initial state

      // Now simulate error state after initial load attempt
      component.iframeError.set(true);
      component.isIframeLoading.set(false);
      fixture.detectChanges();

      const compiled = fixture.nativeElement as HTMLElement;
      expect(compiled.textContent).toContain('metadata.website.failedToLoad');
    });
  });
});
