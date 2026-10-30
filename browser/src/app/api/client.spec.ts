import { TestBed } from '@angular/core/testing';
import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AqlApiClient } from './client';

describe('AqlApiClient', () => {
  let api: AqlApiClient;
  let httpMock: HttpTestingController;

  const countRequest = () =>
    api.request((client, signal) =>
      client.GET('/serps/count', { params: { query: { query: 'test' } }, signal }),
    );

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(AqlApiClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('should send requests via HttpClient and emit the response data', (done: DoneFn) => {
    countRequest().subscribe(count => {
      expect(count).toBe(42);
      done();
    });

    const req = httpMock.expectOne(req => req.url.includes('/serps/count?query=test'));
    expect(req.request.method).toBe('GET');
    req.flush(42);
  });

  it('should error with an HttpErrorResponse on HTTP errors', (done: DoneFn) => {
    countRequest().subscribe({
      error: (error: unknown) => {
        expect(error).toBeInstanceOf(HttpErrorResponse);
        expect((error as HttpErrorResponse).status).toBe(429);
        done();
      },
    });

    httpMock
      .expectOne(req => req.url.includes('/serps/count'))
      .flush({ detail: 'Too many requests' }, { status: 429, statusText: 'Too Many Requests' });
  });

  it('should cancel the request on unsubscribe', () => {
    const subscription = countRequest().subscribe();
    const req = httpMock.expectOne(req => req.url.includes('/serps/count'));

    subscription.unsubscribe();

    expect(req.cancelled).toBeTrue();
  });
});
