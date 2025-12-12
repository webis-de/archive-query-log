import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AppMetadataPanelComponent } from './metadata-panel.component';
import { SearchResult } from '../../models/search.model';
import { SessionService } from '../../services/session.service';
import { signal, WritableSignal } from '@angular/core';

describe('AppMetadataPanelComponent', () => {
  let component: AppMetadataPanelComponent;
  let fixture: ComponentFixture<AppMetadataPanelComponent>;
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
    },
  } as SearchResult;

  beforeEach(async () => {
    mockSessionService = {
      sidebarCollapsed: signal(true),
    };

    await TestBed.configureTestingModule({
      imports: [AppMetadataPanelComponent],
      providers: [{ provide: SessionService, useValue: mockSessionService }],
    }).compileComponents();

    fixture = TestBed.createComponent(AppMetadataPanelComponent);
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
});
