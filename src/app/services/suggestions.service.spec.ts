import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { SuggestionsService } from './suggestions.service';
import { ApiService } from './api.service';
import { SearchResponse } from '../models/search.model';

describe('SuggestionsService', () => {
  let service: SuggestionsService;
  let mockApiService: jasmine.SpyObj<ApiService>;

  const mockSearchResponse: SearchResponse = {
    query: 'test',
    count: 3,
    total: 3,
    page_size: 10,
    total_pages: 1,
    pagination: {
      current_results: 3,
      total_results: 3,
      results_per_page: 10,
      total_pages: 1,
    },
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
    expect(service.MAX_SUGGESTIONS).toBe(5);
  });

  describe('suggestions signal', () => {
    it('should return empty array for queries shorter than minimum length', fakeAsync(() => {
      service.search('ab'); // 2 characters, less than minimum of 3
      tick(350); // Wait for debounce

      expect(service.suggestions()).toEqual([]);
      expect(mockApiService.get).not.toHaveBeenCalled();
    }));

    it('should fetch suggestions for queries with minimum length', fakeAsync(() => {
      service.search('tes'); // Exactly 3 characters
      tick(350); // Wait for debounce

      expect(mockApiService.get).toHaveBeenCalled();
      expect(service.suggestions().length).toBe(2);
    }));

    it('should fetch suggestions for queries longer than minimum length', fakeAsync(() => {
      service.search('testing'); // 7 characters
      tick(350); // Wait for debounce

      expect(mockApiService.get).toHaveBeenCalled();
      expect(service.suggestions().length).toBe(2);
    }));

    it('should debounce rapid queries', fakeAsync(() => {
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
        size: 5,
      });
    }));

    it('should not make duplicate calls for the same query', fakeAsync(() => {
      service.search('test');
      tick(350);
      service.search('test'); // Same query
      tick(350);

      // distinctUntilChanged should prevent duplicate calls
      expect(mockApiService.get).toHaveBeenCalledTimes(1);
    }));

    it('should map results to suggestions correctly', fakeAsync(() => {
      service.search('test');
      tick(350);

      expect(service.suggestions()).toEqual([
        {
          id: 'result-1',
          query: 'test query one',
        },
        {
          id: 'result-2',
          query: 'test query two',
        },
      ]);
    }));

    it('should handle API errors gracefully', fakeAsync(() => {
      mockApiService.get.and.returnValue(throwError(() => new Error('API Error')));

      service.search('test');
      tick(350);

      // Should return empty array on error
      expect(service.suggestions()).toEqual([]);
    }));
  });

  describe('clear suggestions', () => {
    it('should clear suggestions when called with empty string', fakeAsync(() => {
      service.search('test');
      tick(350);
      expect(service.suggestions().length).toBe(2);

      service.search('');
      tick(350);
      expect(service.suggestions()).toEqual([]);
    }));
  });

  describe('search', () => {
    it('should call API with correct parameters', fakeAsync(() => {
      service.search('search term');
      tick(350);

      expect(mockApiService.get).toHaveBeenCalledWith('/api/serps', {
        query: 'search term',
        size: 5,
      });
    }));
  });
});
