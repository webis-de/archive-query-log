import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { SearchViewComponent } from './search-view.component';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';

describe('SearchViewComponent', () => {
  let component: SearchViewComponent;
  let fixture: ComponentFixture<SearchViewComponent>;
  let mockSuggestionsService: jasmine.SpyObj<SuggestionsService>;

  beforeEach(async () => {
    mockSuggestionsService = jasmine.createSpyObj('SuggestionsService', ['search'], {
      MINIMUM_QUERY_LENGTH: 3,
      suggestions: jasmine.createSpy().and.returnValue([]),
    });

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

    it('should trigger search when input has minimum length', () => {
      component.onSearchInput('tes');

      expect(component.searchQuery).toBe('tes');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('tes');
      expect(component.showSuggestions()).toBeTrue();
    });

    it('should clear suggestions when input is shorter than minimum', () => {
      component.onSearchInput('te');

      expect(component.searchQuery).toBe('te');
      expect(mockSuggestionsService.search).toHaveBeenCalledWith('');
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
