import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppQueryMetadataPanelComponent } from './query-metadata-panel.component';
import { SearchResult, SerpDetailsResponse } from '../../models/search.model';
import { SessionService } from '../../services/session.service';
import { SearchService } from '../../services/search.service';
import { ProviderService } from '../../services/provider.service';
import { signal, WritableSignal } from '@angular/core';
import { TranslateModule } from '@ngx-translate/core';
import { of } from 'rxjs';

describe('AppQueryMetadataPanelComponent', () => {
  let component: AppQueryMetadataPanelComponent;
  let fixture: ComponentFixture<AppQueryMetadataPanelComponent>;
  let mockSessionService: { sidebarCollapsed: WritableSignal<boolean> };
  let mockSearchService: jasmine.SpyObj<SearchService>;
  let mockProviderService: jasmine.SpyObj<ProviderService>;

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
    mockSearchService = jasmine.createSpyObj('SearchService', ['getSerpDetails']);
    mockSearchService.getSerpDetails.and.returnValue(
      of({ serp_id: 'test-123', serp: mockSearchResult } as SerpDetailsResponse),
    );
    mockProviderService = jasmine.createSpyObj('ProviderService', ['getProviderById']);
    mockProviderService.getProviderById.and.returnValue(of(null));

    await TestBed.configureTestingModule({
      imports: [AppQueryMetadataPanelComponent, TranslateModule.forRoot()],
      providers: [
        { provide: SessionService, useValue: mockSessionService },
        { provide: SearchService, useValue: mockSearchService },
        { provide: ProviderService, useValue: mockProviderService },
      ],
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
    expect(component.activeTab()).toBe('html');
  });
});
