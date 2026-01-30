import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import { of } from 'rxjs';
import { SearchViewComponent } from './search-view.component';
import { SearchResultItemComponent } from '../../components/search-result-item/search-result-item.component';
import { SuggestionsService, Suggestion } from '../../services/suggestions.service';
import { ProviderService } from '../../services/provider.service';
import { SearchService } from '../../services/search.service';
import { SearchResponse, QueryMetadataResponse } from '../../models/search.model';

describe('SearchViewComponent', () => {
  let component: SearchViewComponent;
  let fixture: ComponentFixture<SearchViewComponent>;
  let mockSuggestionsService: jasmine.SpyObj<SuggestionsService>;
  let mockProviderService: jasmine.SpyObj<ProviderService>;
  let mockSearchService: jasmine.SpyObj<SearchService>;
  let mockRouter: jasmine.SpyObj<Router>;

  const mockSearchResponse: SearchResponse = {
    query: '',
    count: 0,
    total: 0,
    page_size: 10,
    total_pages: 0,
    results: [],
    pagination: {
      current_results: 0,
      total_results: 0,
      results_per_page: 10,
      total_pages: 0,
    },
    fuzzy: false,
    fuzziness: null,
    expand_synonyms: false,
  };

  beforeEach(async () => {
    mockSuggestionsService = jasmine.createSpyObj('SuggestionsService', ['search'], {
      MINIMUM_QUERY_LENGTH: 3,
      suggestionsWithMeta: signal([]),
      search: jasmine.createSpy('search'),
    } as unknown as jasmine.SpyObj<SuggestionsService>);
    mockProviderService = jasmine.createSpyObj('ProviderService', ['getProviders']);
    mockProviderService.getProviders.and.returnValue(of([]));
    mockSearchService = jasmine.createSpyObj('SearchService', [
      'search',
      'searchWithParams',
      'getQueryMetadata',
    ]);
    mockSearchService.search.and.returnValue(of(mockSearchResponse));
    mockSearchService.searchWithParams.and.returnValue(of(mockSearchResponse));
    mockSearchService.getQueryMetadata.and.returnValue(
      of({
        query: '',
        total_hits: 0,
        top_queries: [],
        date_histogram: [],
        top_providers: [],
        top_archives: [],
      } as QueryMetadataResponse),
    );

    mockRouter = jasmine.createSpyObj('Router', ['navigate']);

    await TestBed.configureTestingModule({
      imports: [SearchViewComponent, SearchResultItemComponent, TranslateModule.forRoot()],
      providers: [
        {
          provide: ActivatedRoute,
          useValue: {
            paramMap: of(new Map()),
            queryParamMap: of(new Map()),
          },
        },
        { provide: SuggestionsService, useValue: mockSuggestionsService },
        { provide: ProviderService, useValue: mockProviderService },
        { provide: SearchService, useValue: mockSearchService },
        { provide: Router, useValue: mockRouter },
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

    it('should navigate with year param when histogram click occurs', () => {
      component.searchQuery = 'test';

      const payload: Parameters<SearchViewComponent['onMetadataHistogramClick']>[0] = {
        year: '2024',
      };
      component.onMetadataHistogramClick(payload);

      expect(mockRouter.navigate).toHaveBeenCalledWith(['/serps/search'], {
        queryParams: { q: 'test', year: '2024' },
      });
    });

    it('should set initialFilters dateFrom and dateTo when year is clicked', () => {
      component.searchQuery = 'test';

      const payload: Parameters<SearchViewComponent['onMetadataHistogramClick']>[0] = {
        year: '2024',
      };
      component.onMetadataHistogramClick(payload);

      expect(component.initialFilters?.dateFrom).toContain('2024');
      expect(component.initialFilters?.dateTo).toContain('2024');
    });

    it('should include year when performing search after year filter set', () => {
      component.searchQuery = 'hello';
      component.metadataYear.set('2024');
      component.onSearch();

      expect(mockSearchService.search).toHaveBeenCalled();
      const lastCallArgs = (mockSearchService.search as jasmine.Spy).calls.mostRecent().args;
      // args: query, pageSize, offset, options
      expect(lastCallArgs[0]).toBe('hello');
      expect(lastCallArgs[3]).toBeDefined();
      expect(lastCallArgs[3].year).toBe(2024);
    });
  });
});
