import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { MetadataUnbrandedTabComponent } from './metadata-unbranded-tab.component';
import { UnbrandedSerp } from '../../../models/search.model';

describe('MetadataUnbrandedTabComponent', () => {
  @Component({
    selector: 'app-test-host',
    template: `
      <app-metadata-unbranded-tab
        [unbranded]="unbranded"
        [isLoading]="isLoading"
      ></app-metadata-unbranded-tab>
    `,
    standalone: true,
    imports: [MetadataUnbrandedTabComponent],
  })
  class TestHostComponent {
    unbranded: UnbrandedSerp | null = null;
    isLoading = false;
  }

  let hostFixture: ComponentFixture<TestHostComponent>;
  let hostComponent: TestHostComponent;
  let translate: TranslateService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [TestHostComponent, TranslateModule.forRoot()],
    }).compileComponents();

    hostFixture = TestBed.createComponent(TestHostComponent);
    hostComponent = hostFixture.componentInstance;
    translate = TestBed.inject(TranslateService);

    // Provide minimal translations used in the template
    translate.setTranslation('en', {
      metadata: {
        unbrandedView: 'Unbranded View',
        noUnbrandedData: 'Unbranded view not available',
        unbranded: { noResults: 'No results' },
        timestamp: 'Timestamp',
      },
    });
    translate.use('en');

    hostFixture.detectChanges();
  });

  it('should create host and child', () => {
    expect(hostComponent).toBeTruthy();
  });

  it('shows no unbranded data message when no data', () => {
    hostComponent.unbranded = null;
    hostComponent.isLoading = false;
    hostFixture.detectChanges();

    const text = hostFixture.nativeElement.textContent;
    expect(text).toContain('Unbranded view not available');
  });

  it('shows loading spinner when loading', () => {
    hostComponent.isLoading = true;
    hostFixture.detectChanges();

    const spinner = hostFixture.nativeElement.querySelector('.loading-spinner');
    expect(spinner).toBeTruthy();
  });

  it('shows no results message when data present but no results', () => {
    hostComponent.unbranded = {
      serp_id: 'test-serp-empty',
      query: { raw: 'raw', parsed: '' },
      results: [],
      metadata: { timestamp: '', url: '', status_code: 200 },
    } as UnbrandedSerp;
    hostComponent.isLoading = false;
    hostFixture.detectChanges();

    const el = hostFixture.nativeElement;
    expect(el.textContent).toContain('No results');
  });

  it('renders results, count, query and timestamp when data present', () => {
    hostComponent.unbranded = {
      serp_id: 'test-serp-1',
      query: { raw: 'raw', parsed: 'parsed query' },
      results: [
        {
          title: 'Example Title',
          url: 'https://example.com',
          snippet: 'This is a snippet',
          position: 1,
        },
      ],
      metadata: { timestamp: '2020-01-01', url: 'https://example.com', status_code: 200 },
    } as UnbrandedSerp;
    hostComponent.isLoading = false;
    hostFixture.detectChanges();

    const el = hostFixture.nativeElement;

    // header badge shows results length
    const headerBadge = el.querySelector('.badge-outline');
    expect(headerBadge.textContent.trim()).toBe('1');

    // search input shows parsed query
    const input = el.querySelector('input[type="text"]') as HTMLInputElement;
    expect(input.value).toBe('parsed query');

    // timestamp displayed
    expect(el.textContent).toContain('Timestamp 2020-01-01');

    // result panel shows snippet and position badge
    expect(el.textContent).toContain('This is a snippet');
    expect(el.querySelector('.badge-primary').textContent.trim()).toBe('1');
  });
});
