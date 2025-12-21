import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { SuggestionsService, Suggestion } from './suggestions.service';
import { ApiService } from './api.service';
import { SearchResponse } from '../models/search.model';

describe('SuggestionsService', () => {
  let service: SuggestionsService;
  let mockApiService: jasmine.SpyObj<ApiService>;

  const mockSearchResponse: SearchResponse = {
    count: 3,
    results: [
      {
        _index: 'test-index',
        _type: 'test-type',
        _id: 'result-1',
        _score: 1.5,
        _source: {
          last_modified: '2024-01-01T00:00:00Z',
          archive: {
            id: 'archive-1',
            cdx_api_url: 'http://example.com/cdx',
            memento_api_url: 'http://example.com/memento',
            priority: 1,
          },
          provider: {
            id: 'provider-1',
            domain: 'example.com',
            url_path_prefix: '/',
            priority: 1,
          },
          capture: {
            id: 'capture-1',
            url: 'http://example.com/page1',
            timestamp: '2024-01-01T00:00:00Z',
            status_code: 200,
            digest: 'abc123',
            mimetype: 'text/html',
          },
          url_query: 'test query one',
          url_query_parser: { should_parse: true },
          url_page_parser: { should_parse: true },
          url_offset_parser: { should_parse: false },
          warc_query_parser: { should_parse: false },
          warc_snippets_parser: { should_parse: false },
        },
      },
      {
        _index: 'test-index',
        _type: 'test-type',
        _id: 'result-2',
        _score: 1.2,
        _source: {
          last_modified: '2024-01-02T00:00:00Z',
          archive: {
            id: 'archive-1',
            cdx_api_url: 'http://example.com/cdx',
            memento_api_url: 'http://example.com/memento',
            priority: 1,
          },
          provider: {
            id: 'provider-2',
            domain: 'example2.com',
            url_path_prefix: '/',
            priority: 2,
          },
          capture: {
            id: 'capture-2',
            url: 'http://example2.com/page2',
            timestamp: '2024-01-02T00:00:00Z',
            status_code: 200,
            digest: 'def456',
            mimetype: 'text/html',
          },
          url_query: 'test query two',
          url_query_parser: { should_parse: true },
          url_page_parser: { should_parse: true },
          url_offset_parser: { should_parse: false },
          warc_query_parser: { should_parse: false },
          warc_snippets_parser: { should_parse: false },
        },
      },
    ],
  };

  beforeEach(() => {
    mockApiService = jasmine.createSpyObj('ApiService', ['get']);
    mockApiService.get.and.returnValue(of(mockSearchResponse));

    TestBed.configureTestingModule({
      providers: [SuggestionsService, { provide: ApiService, useValue: mockApiService }],
    });
    service = TestBed.inject(SuggestionsService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should have correct constants', () => {
    expect(service.MINIMUM_QUERY_LENGTH).toBe(3);
    expect(service.DEBOUNCE_TIME_MS).toBe(300);
    expect(service.MAX_SUGGESTIONS).toBe(10);
  });

  describe('getSuggestions$', () => {
    it('should return empty array for queries shorter than minimum length', fakeAsync(() => {
      let suggestions: Suggestion[] = [];
      service.getSuggestions$().subscribe(result => {
        suggestions = result;
      });

      service.search('ab'); // 2 characters, less than minimum of 3
      tick(350); // Wait for debounce

      expect(suggestions).toEqual([]);
      expect(mockApiService.get).not.toHaveBeenCalled();
    }));

    it('should fetch suggestions for queries with minimum length', fakeAsync(() => {
      let suggestions: Suggestion[] = [];
      service.getSuggestions$().subscribe(result => {
        suggestions = result;
      });

      service.search('tes'); // Exactly 3 characters
      tick(350); // Wait for debounce

      expect(mockApiService.get).toHaveBeenCalled();
      expect(suggestions.length).toBe(2);
    }));

    it('should fetch suggestions for queries longer than minimum length', fakeAsync(() => {
      let suggestions: Suggestion[] = [];
      service.getSuggestions$().subscribe(result => {
        suggestions = result;
      });

      service.search('testing'); // 7 characters
      tick(350); // Wait for debounce

      expect(mockApiService.get).toHaveBeenCalled();
      expect(suggestions.length).toBe(2);
    }));

    it('should debounce rapid queries', fakeAsync(() => {
      service.getSuggestions$().subscribe();

      service.search('test1');
      tick(100);
      service.search('test2');
      tick(100);
      service.search('test3');
      tick(350); // Wait for final debounce

      // Should only make one API call with the last value
      expect(mockApiService.get).toHaveBeenCalledTimes(1);
      expect(mockApiService.get).toHaveBeenCalledWith('/api/serps', {
        query: 'test3',
        size: 10,
      });
    }));

    it('should not make duplicate calls for the same query', fakeAsync(() => {
      service.getSuggestions$().subscribe();

      service.search('test');
      tick(350);
      service.search('test'); // Same query
      tick(350);

      // distinctUntilChanged should prevent duplicate calls
      expect(mockApiService.get).toHaveBeenCalledTimes(1);
    }));

    it('should map results to suggestions correctly', fakeAsync(() => {
      let suggestions: Suggestion[] = [];
      service.getSuggestions$().subscribe(result => {
        suggestions = result;
      });

      service.search('test');
      tick(350);

      expect(suggestions).toEqual([
        {
          id: 'result-1',
          query: 'test query one',
          url: 'http://example.com/page1',
        },
        {
          id: 'result-2',
          query: 'test query two',
          url: 'http://example2.com/page2',
        },
      ]);
    }));

    it('should handle API errors gracefully', fakeAsync(() => {
      mockApiService.get.and.returnValue(throwError(() => new Error('API Error')));

      let suggestions: Suggestion[] = [{ id: 'old', query: 'old', url: 'old' }];
      let errorOccurred = false;

      service.getSuggestions$().subscribe({
        next: result => {
          suggestions = result;
        },
        error: () => {
          errorOccurred = true;
        },
      });

      service.search('test');
      tick(350);

      // Should return empty array on error, not propagate the error
      expect(suggestions).toEqual([]);
      expect(errorOccurred).toBeFalse();
    }));
  });

  describe('clear', () => {
    it('should clear suggestions when called', fakeAsync(() => {
      let suggestions: Suggestion[] = [];
      service.getSuggestions$().subscribe(result => {
        suggestions = result;
      });

      service.search('test');
      tick(350);
      expect(suggestions.length).toBe(2);

      service.clear();
      tick(350);
      expect(suggestions).toEqual([]);
    }));
  });

  describe('search', () => {
    it('should call API with correct parameters', fakeAsync(() => {
      service.getSuggestions$().subscribe();

      service.search('search term');
      tick(350);

      expect(mockApiService.get).toHaveBeenCalledWith('/api/serps', {
        query: 'search term',
        size: 10,
      });
    }));
  });
});
