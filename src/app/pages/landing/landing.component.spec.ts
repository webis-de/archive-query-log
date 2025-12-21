import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Router, ActivatedRoute } from '@angular/router';
import { of, Subject } from 'rxjs';
import { LandingComponent } from './landing.component';
import { SearchHistoryService } from '../../services/search-history.service';
import { ProjectService } from '../../services/project.service';
import { SessionService } from '../../services/session.service';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';

describe('LandingComponent', () => {
  let component: LandingComponent;
  let fixture: ComponentFixture<LandingComponent>;
  let mockRouter: jasmine.SpyObj<Router>;
  let mockActivatedRoute: jasmine.SpyObj<ActivatedRoute>;
  let mockSearchHistoryService: jasmine.SpyObj<SearchHistoryService>;
  let mockProjectService: jasmine.SpyObj<ProjectService>;
  let mockSessionService: jasmine.SpyObj<SessionService>;
  let mockSuggestionsService: jasmine.SpyObj<SuggestionsService>;
  let suggestionsSubject: Subject<Suggestion[]>;

  beforeEach(async () => {
    suggestionsSubject = new Subject<Suggestion[]>();

    mockRouter = jasmine.createSpyObj('Router', ['navigate']);
    mockActivatedRoute = jasmine.createSpyObj('ActivatedRoute', [], {
      queryParams: of({}),
    });
    mockSearchHistoryService = jasmine.createSpyObj('SearchHistoryService', ['addSearch']);
    mockProjectService = jasmine.createSpyObj('ProjectService', [], {
      projects: jasmine.createSpy().and.returnValue([]),
    });
    mockSessionService = jasmine.createSpyObj('SessionService', [], {
      session: jasmine.createSpy().and.returnValue(null),
    });
    mockSuggestionsService = jasmine.createSpyObj(
      'SuggestionsService',
      ['getSuggestions$', 'search', 'clear'],
      {
        MINIMUM_QUERY_LENGTH: 3,
      },
    );
    mockSuggestionsService.getSuggestions$.and.returnValue(suggestionsSubject.asObservable());

    await TestBed.configureTestingModule({
      imports: [LandingComponent],
      providers: [
        { provide: Router, useValue: mockRouter },
        { provide: ActivatedRoute, useValue: mockActivatedRoute },
        { provide: SearchHistoryService, useValue: mockSearchHistoryService },
        { provide: ProjectService, useValue: mockProjectService },
        { provide: SessionService, useValue: mockSessionService },
        { provide: SuggestionsService, useValue: mockSuggestionsService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(LandingComponent);
    component = fixture.componentInstance;
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
    const mockSearchItem = {
      id: 'test-id',
      projectId: 'project-1',
      filter: { query: 'test query' },
      createdAt: new Date().toISOString(),
      label: 'test query',
    };
    mockSearchHistoryService.addSearch.and.returnValue(mockSearchItem);

    component.searchQuery.set('test query');
    component.onSearch();

    expect(mockSearchHistoryService.addSearch).toHaveBeenCalledWith({ query: 'test query' });
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/s', 'test-id'], {
      queryParams: { q: 'test query' },
    });
  });

  it('should navigate to temporary search in temp mode', () => {
    component.isTemporaryMode.set(true);
    component.searchQuery.set('temp query');
    component.onSearch();

    expect(mockRouter.navigate).toHaveBeenCalledWith(['/s', 'temp'], {
      queryParams: { q: 'temp query' },
    });
  });

  it('should display correct landing message when no projects exist', () => {
    expect(component.landingMessage()).toBe('Create your first project and start searching');
  });

  describe('Suggestions', () => {
    it('should initialize with empty suggestions', () => {
      expect(component.suggestions()).toEqual([]);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should subscribe to suggestions on init', () => {
      expect(mockSuggestionsService.getSuggestions$).toHaveBeenCalled();
    });

    it('should update suggestions when service emits', () => {
      const mockSuggestions: Suggestion[] = [
        { id: '1', query: 'test query', url: 'http://example.com' },
      ];

      // Set a non-empty search query first
      component.searchQuery.set('test');
      suggestionsSubject.next(mockSuggestions);

      expect(component.suggestions()).toEqual(mockSuggestions);
      expect(component.showSuggestions()).toBeTrue();
    });

    it('should not show suggestions when search query is empty even if suggestions are returned', () => {
      const mockSuggestions: Suggestion[] = [
        { id: '1', query: 'test query', url: 'http://example.com' },
      ];

      component.searchQuery.set('');
      suggestionsSubject.next(mockSuggestions);

      expect(component.suggestions()).toEqual(mockSuggestions);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should not show suggestions when empty array is emitted', () => {
      suggestionsSubject.next([]);

      expect(component.suggestions()).toEqual([]);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should trigger search when input has minimum length', () => {
      component.onSearchInput('tes');

      expect(component.searchQuery()).toBe('tes');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('tes');
    });

    it('should not trigger search when input is shorter than minimum', () => {
      component.onSearchInput('te');

      expect(component.searchQuery()).toBe('te');
      expect(mockSuggestionsService.search).not.toHaveBeenCalled();
      expect(component.suggestions()).toEqual([]);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should select suggestion and trigger search', () => {
      const mockSearchItem = {
        id: 'test-id',
        projectId: 'project-1',
        filter: { query: 'selected query' },
        createdAt: new Date().toISOString(),
        label: 'selected query',
      };
      mockSearchHistoryService.addSearch.and.returnValue(mockSearchItem);

      const suggestion: Suggestion = {
        id: '1',
        query: 'selected query',
        url: 'http://example.com',
      };

      component.onSuggestionSelect(suggestion);

      expect(component.searchQuery()).toBe('selected query');
      expect(component.showSuggestions()).toBeFalse();
      expect(mockRouter.navigate).toHaveBeenCalled();
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
