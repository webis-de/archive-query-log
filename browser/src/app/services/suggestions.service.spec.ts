import { TestBed, fakeAsync, tick, flushMicrotasks } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { SuggestionsService } from './suggestions.service';
import { SearchService } from './search.service';

describe('SuggestionsService', () => {
  let service: SuggestionsService;
  let mockSearchService: jasmine.SpyObj<SearchService>;

  const mockSuggestionsResponse = {
    completions: [
      { text: 'test query one', score: 1, frequency: 12 },
      { text: 'test query two', score: 1, frequency: 3 },
    ],
    corrections: [],
  };

  beforeEach(() => {
    mockSearchService = jasmine.createSpyObj('SearchService', ['suggestQueries']);
    mockSearchService.suggestQueries.and.returnValue(of(mockSuggestionsResponse));
    TestBed.configureTestingModule({
      providers: [SuggestionsService, { provide: SearchService, useValue: mockSearchService }],
    });
  });

  beforeEach(() => {
    service = TestBed.inject(SuggestionsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should have correct constants', () => {
    expect(service.MINIMUM_QUERY_LENGTH).toBe(3);
    expect(service.DEBOUNCE_TIME_MS).toBe(300);
    expect(service.MAX_SUGGESTIONS).toBe(5);
  });

  describe('suggestions signal', () => {
    it('should return empty array for queries shorter than minimum length', fakeAsync(() => {
      service.search('ab'); // 2 characters, less than minimum of 3
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      expect(service.suggestions()).toEqual([]);
      expect(mockSearchService.suggestQueries).not.toHaveBeenCalled();
    }));

    it('should fetch suggestions for queries with minimum length', fakeAsync(() => {
      service.search('tes'); // Exactly 3 characters
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      expect(mockSearchService.suggestQueries).toHaveBeenCalled();
      expect(service.suggestions().length).toBe(2);
    }));

    it('should fetch suggestions for queries longer than minimum length', fakeAsync(() => {
      service.search('testing'); // 7 characters
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      expect(mockSearchService.suggestQueries).toHaveBeenCalled();
      expect(service.suggestions().length).toBe(2);
    }));

    it('should debounce rapid queries', fakeAsync(() => {
      service.search('test1');
      tick(100);
      service.search('test2');
      tick(100);
      service.search('test3');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      // We should only call the search API once for the input
      expect(mockSearchService.suggestQueries).toHaveBeenCalledTimes(1);
      expect(mockSearchService.suggestQueries).toHaveBeenCalledWith('test3', 5);
    }));

    it('should not make duplicate calls for the same query', fakeAsync(() => {
      service.search('test');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();
      mockSearchService.suggestQueries.calls.reset();
      service.search('test'); // Same query
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      // distinctUntilChanged should prevent duplicate calls
      expect(mockSearchService.suggestQueries).toHaveBeenCalledTimes(0);
    }));

    it('should map results to suggestions correctly', fakeAsync(() => {
      service.search('test');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      expect(service.suggestions()).toEqual([
        {
          id: 'test query one',
          query: 'test query one',
          score: 12,
        },
        {
          id: 'test query two',
          query: 'test query two',
          score: 3,
        },
      ]);
    }));

    it('should handle API errors gracefully', fakeAsync(() => {
      // Create new service instance with error response
      mockSearchService.suggestQueries.and.returnValue(throwError(() => new Error('API Error')));
      const errorService = TestBed.inject(SuggestionsService);

      errorService.search('test');
      tick(errorService.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      // Should return empty array on error
      expect(errorService.suggestions()).toEqual([]);
    }));
  });

  describe('clear suggestions', () => {
    it('should clear suggestions when called with empty string', fakeAsync(() => {
      service.search('test');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();
      expect(service.suggestions().length).toBe(2);

      service.search('');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();
      expect(service.suggestions()).toEqual([]);
    }));
  });

  describe('search', () => {
    it('should call API with correct parameters', fakeAsync(() => {
      service.search('search term');
      tick(service.DEBOUNCE_TIME_MS);
      flushMicrotasks();

      expect(mockSearchService.suggestQueries).toHaveBeenCalledWith('search term', 5);
    }));
  });
});
