import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { of, Subject } from 'rxjs';
import { SearchViewComponent } from './search-view.component';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';

describe('SearchViewComponent', () => {
  let component: SearchViewComponent;
  let fixture: ComponentFixture<SearchViewComponent>;
  let mockSuggestionsService: jasmine.SpyObj<SuggestionsService>;
  let suggestionsSubject: Subject<Suggestion[]>;

  beforeEach(async () => {
    suggestionsSubject = new Subject<Suggestion[]>();

    mockSuggestionsService = jasmine.createSpyObj(
      'SuggestionsService',
      ['getSuggestions$', 'search', 'clear'],
      {
        MINIMUM_QUERY_LENGTH: 3,
      },
    );
    mockSuggestionsService.getSuggestions$.and.returnValue(suggestionsSubject.asObservable());

    await TestBed.configureTestingModule({
      imports: [SearchViewComponent],
      providers: [
        provideHttpClient(),
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: of(new Map()),
            queryParamMap: of(new Map()),
          },
        },
        { provide: SuggestionsService, useValue: mockSuggestionsService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
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
      const mockSuggestions: Suggestion[] = [{ id: '1', query: 'test query' }];

      // Set a non-empty search query first
      component.searchQuery = 'test';
      suggestionsSubject.next(mockSuggestions);

      expect(component.suggestions()).toEqual(mockSuggestions);
      expect(component.showSuggestions()).toBeTrue();
    });

    it('should not show suggestions when search query is empty even if suggestions are returned', () => {
      const mockSuggestions: Suggestion[] = [{ id: '1', query: 'test query' }];

      component.searchQuery = '';
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

      expect(component.searchQuery).toBe('tes');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('tes');
    });

    it('should not trigger search when input is shorter than minimum', () => {
      component.onSearchInput('te');

      expect(component.searchQuery).toBe('te');
      expect(mockSuggestionsService.search).not.toHaveBeenCalled();
      expect(component.suggestions()).toEqual([]);
      expect(component.showSuggestions()).toBeFalse();
    });

    it('should select suggestion and hide dropdown', () => {
      const suggestion: Suggestion = {
        id: '1',
        query: 'selected query',
      };

      component.onSuggestionSelect(suggestion);

      expect(component.searchQuery).toBe('selected query');
      expect(component.showSuggestions()).toBeFalse();
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
