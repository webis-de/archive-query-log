import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { ProviderService, ProvidersApiResponse, ProviderDetailResponse } from './provider.service';
import { environment } from '../../environments/environment';

describe('ProviderService', () => {
  let service: ProviderService;
  let httpMock: HttpTestingController;

  const mockApiResponse: ProvidersApiResponse = {
    count: 4,
    results: [
      { _id: 'google', _source: { name: 'Google' } },
      { _id: 'bing', _source: { name: 'Bing' } },
      { _id: 'duckduckgo', _source: { name: 'DuckDuckGo' } },
      { _id: 'yahoo', _source: { name: 'Yahoo' } },
    ],
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [ProviderService, provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(ProviderService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    service.clearCache();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should fetch providers from API', (done: DoneFn) => {
    service.getProviders().subscribe(providers => {
      expect(providers.length).toBe(4);
      expect(providers[0].id).toBe('bing'); // Sorted alphabetically
      expect(providers[0].name).toBe('Bing');
      done();
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    expect(req.request.method).toBe('GET');
    req.flush(mockApiResponse);
  });

  it('should sort providers alphabetically by name', (done: DoneFn) => {
    service.getProviders().subscribe(providers => {
      const names = providers.map(p => p.name);
      const sortedNames = [...names].sort((a, b) => a.localeCompare(b));
      expect(names).toEqual(sortedNames);
      done();
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    req.flush(mockApiResponse);
  });

  it('should cache the providers response', (done: DoneFn) => {
    // First call
    service.getProviders().subscribe(() => {
      // Second call should use cache
      service.getProviders().subscribe(providers => {
        expect(providers.length).toBe(4);
        done();
      });
    });

    // Only one request should be made
    const req = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    req.flush(mockApiResponse);
  });

  it('should return empty array on error', (done: DoneFn) => {
    service.getProviders().subscribe(providers => {
      expect(providers).toEqual([]);
      done();
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    req.error(new ErrorEvent('Network error'));
  });

  it('should clear cache when clearCache is called', (done: DoneFn) => {
    // First call
    service.getProviders().subscribe(() => {
      service.clearCache();

      // After clearing cache, another request should be made
      service.getProviders().subscribe(providers => {
        expect(providers.length).toBe(4);
        done();
      });

      const req2 = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
      req2.flush(mockApiResponse);
    });

    const req1 = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    req1.flush(mockApiResponse);
  });

  it('should map API response to ProviderOption format', (done: DoneFn) => {
    service.getProviders().subscribe(providers => {
      providers.forEach(provider => {
        expect(provider).toEqual(
          jasmine.objectContaining({
            id: jasmine.any(String),
            name: jasmine.any(String),
          }),
        );
      });
      done();
    });

    const req = httpMock.expectOne(`${environment.apiUrl}/api/providers`);
    req.flush(mockApiResponse);
  });

  describe('getProviderById', () => {
    const mockProviderDetailResponse: ProviderDetailResponse = {
      provider_id: 'google',
      provider: {
        _id: 'google',
        _source: {
          name: 'Google',
          domains: ['google.com', 'google.de', 'google.co.uk'],
          url_patterns: ['/search?q=', '/webhp?q='],
          priority: 1,
        },
      },
    };

    it('should fetch provider details by ID', (done: DoneFn) => {
      service.getProviderById('google').subscribe(provider => {
        expect(provider).toBeTruthy();
        expect(provider?.id).toBe('google');
        expect(provider?.name).toBe('Google');
        expect(provider?.domains).toEqual(['google.com', 'google.de', 'google.co.uk']);
        expect(provider?.url_patterns).toEqual(['/search?q=', '/webhp?q=']);
        expect(provider?.priority).toBe(1);
        done();
      });

      const req = httpMock.expectOne(`${environment.apiUrl}/api/providers/google`);
      expect(req.request.method).toBe('GET');
      req.flush(mockProviderDetailResponse);
    });

    it('should return null on error', (done: DoneFn) => {
      service.getProviderById('unknown').subscribe(provider => {
        expect(provider).toBeNull();
        done();
      });

      const req = httpMock.expectOne(`${environment.apiUrl}/api/providers/unknown`);
      req.error(new ErrorEvent('Network error'));
    });

    it('should handle missing optional fields', (done: DoneFn) => {
      const minimalResponse: ProviderDetailResponse = {
        provider_id: 'minimal',
        provider: {
          _id: 'minimal',
          _source: {
            name: 'Minimal Provider',
          },
        },
      };

      service.getProviderById('minimal').subscribe(provider => {
        expect(provider).toBeTruthy();
        expect(provider?.id).toBe('minimal');
        expect(provider?.name).toBe('Minimal Provider');
        expect(provider?.domains).toEqual([]);
        expect(provider?.url_patterns).toEqual([]);
        expect(provider?.priority).toBeUndefined();
        done();
      });

      const req = httpMock.expectOne(`${environment.apiUrl}/api/providers/minimal`);
      req.flush(minimalResponse);
    });
  });
});
