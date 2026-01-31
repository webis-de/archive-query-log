import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, ActivatedRoute } from '@angular/router';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { BehaviorSubject, of } from 'rxjs';
import { LandingComponent } from './landing.component';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { ProviderService } from '../../services/provider.service';
import { SearchFilter, SearchHistoryItem } from '../../models/project.model';

describe('LandingComponent', () => {
  let component: LandingComponent;
  let fixture: ComponentFixture<LandingComponent>;
  let mockRouter: jasmine.SpyObj<Router>;
  let mockSearchHistoryService: jasmine.SpyObj<SearchHistoryService>;
  let mockProjectService: jasmine.SpyObj<ProjectService>;
  let mockSessionService: jasmine.SpyObj<SessionService>;
  let mockSuggestionsService: jasmine.SpyObj<SuggestionsService>;
  let mockProviderService: jasmine.SpyObj<ProviderService>;
  let queryParamsSubject: BehaviorSubject<Record<string, string>>;
  let translateService: TranslateService;

  beforeEach(async () => {
    queryParamsSubject = new BehaviorSubject<Record<string, string>>({});

    mockRouter = jasmine.createSpyObj('Router', ['navigate']);
    mockSearchHistoryService = jasmine.createSpyObj('SearchHistoryService', ['addSearch']);
    mockSearchHistoryService.addSearch.and.returnValue({ id: 'test-id' } as SearchHistoryItem);
    mockProjectService = jasmine.createSpyObj('ProjectService', [], {
      projects: jasmine.createSpy().and.returnValue([]),
    });
    mockSessionService = jasmine.createSpyObj('SessionService', [], {
      session: jasmine.createSpy().and.returnValue(null),
    });
    mockSuggestionsService = jasmine.createSpyObj('SuggestionsService', ['search'], {
      MINIMUM_QUERY_LENGTH: 3,
      suggestionsWithMeta: jasmine.createSpy().and.returnValue([]),
    });
    mockProviderService = jasmine.createSpyObj('ProviderService', ['getProviders']);
    mockProviderService.getProviders.and.returnValue(of([]));

    await TestBed.configureTestingModule({
      imports: [LandingComponent, TranslateModule.forRoot()],
      providers: [
        { provide: Router, useValue: mockRouter },
        {
          provide: ActivatedRoute,
          useValue: {
            queryParams: queryParamsSubject.asObservable(),
          },
        },
        { provide: SearchHistoryService, useValue: mockSearchHistoryService },
        { provide: ProjectService, useValue: mockProjectService },
        { provide: SessionService, useValue: mockSessionService },
        { provide: SuggestionsService, useValue: mockSuggestionsService },
        { provide: ProviderService, useValue: mockProviderService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LandingComponent);
    component = fixture.componentInstance;
    translateService = TestBed.inject(TranslateService);
    translateService.setDefaultLang('en');
    translateService.use('en');
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize with empty search query', () => {
    expect(component.searchQuery()).toBe('');
  });

  it('should not navigate when search query is empty', () => {
    component.searchQuery.set('');
    component.onSearch();
    expect(mockRouter.navigate).not.toHaveBeenCalled();
  });

  it('should navigate to search when query is provided', () => {
    component.searchQuery.set('test query');
    component.onSearch();

    expect(mockSearchHistoryService.addSearch).toHaveBeenCalledWith({
      query: 'test query',
      provider: undefined,
    } as SearchFilter);
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/serps'], {
      queryParams: { q: 'test query', sid: 'test-id' },
    });
  });

  it('should not navigate to temporary search in normal mode', () => {
    component.searchQuery.set('test query');
    component.onSearch();

    // Should navigate to /serps, not a temporary route
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/serps'], {
      queryParams: { q: 'test query', sid: 'test-id' },
    });
  });

  it('should display correct landing message when no projects exist', () => {
    const expected = translateService.instant('landing.createProjectHint');
    expect(component.landingMessage()).toBe(expected);
  });

  describe('Suggestions', () => {
    it('should initialize with empty suggestions', () => {
      expect(component.suggestions()).toEqual([]);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should trigger search when input has minimum length', () => {
      component.onSearchInput('tes');

      expect(component.searchQuery()).toBe('tes');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('tes');
      expect(component.showSuggestions()).toBeTrue();
    });

    it('should clear suggestions when input is shorter than minimum', () => {
      component.onSearchInput('te');

      expect(component.searchQuery()).toBe('te');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('');
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should select suggestion and trigger search', () => {
      const suggestion: Suggestion = {
        id: '1',
        query: 'selected query',
      };

      component.onSuggestionSelect(suggestion);

      expect(component.searchQuery()).toBe('selected query');
      expect(component.showSuggestions()).toBeFalse();
      expect(mockRouter.navigate).toHaveBeenCalledWith(['/serps'], {
        queryParams: { q: 'selected query', sid: 'test-id' },
      });
    });

    it('should render suggestion scores in the landing dropdown', () => {
      const suggestions: Suggestion[] = [
        { id: 's1', query: 'landing one', score: 42 },
        { id: 's2', query: 'landing two', score: 7 },
      ];
      mockSuggestionsService.suggestionsWithMeta.and.returnValue(suggestions);

      component.onSearchInput('tes');
      fixture.detectChanges();

      const text = fixture.nativeElement.textContent;
      expect(text).toContain('landing one');
      expect(text).toContain('42');
      expect(text).toContain('landing two');
      expect(text).toContain('7');
    });

    it('should hide suggestions when clicking outside search container', () => {
      component.showSuggestions.set(true);

      // Simulate clicking outside by creating a mock event with a target outside the container
      const outsideElement = document.createElement('div');
      document.body.appendChild(outsideElement);
      const event = new MouseEvent('click', { bubbles: true });
      Object.defineProperty(event, 'target', { value: outsideElement });

      component.onDocumentClick(event);

      expect(component.showSuggestions()).toBeFalse();
      document.body.removeChild(outsideElement);
    });
  });
});
