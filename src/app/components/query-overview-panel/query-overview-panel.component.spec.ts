import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TranslateModule } from '@ngx-translate/core';
import { QueryMetadataPanelComponent } from './query-metadata-panel.component';
import { QueryMetadataResponse } from '../../models/search.model';

describe('QueryMetadataPanelComponent', () => {
  let component: QueryMetadataPanelComponent;
  let fixture: ComponentFixture<QueryMetadataPanelComponent>;

  const mockMetadata: QueryMetadataResponse = {
    query: 'neural network',
    total_hits: 12000,
    top_queries: [
      { key: 'neural nets', count: 120 },
      { key: 'deep learning', count: 95 },
    ],
    date_histogram: [{ key_as_string: '2024-01-01T00:00:00Z', count: 500 }],
    top_providers: [{ domain: 'example.com', count: 42 }],
    top_archives: [{ name: 'Archive.org', count: 18 }],
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [QueryMetadataPanelComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(QueryMetadataPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display the response query when available', () => {
    fixture.componentRef.setInput('data', mockMetadata);
    fixture.componentRef.setInput('query', 'fallback query');
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('neural network');
  });

  it('should fall back to the input query when response query is missing', () => {
    fixture.componentRef.setInput('data', { ...mockMetadata, query: '' });
    fixture.componentRef.setInput('query', 'fallback query');
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('fallback query');
  });

  it('should render total hits when available', () => {
    fixture.componentRef.setInput('data', mockMetadata);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('12,000');
  });

  it('should show no data label when lists are empty', () => {
    fixture.componentRef.setInput('data', {
      query: 'empty',
      total_hits: 0,
      top_queries: [],
      date_histogram: [],
      top_providers: [],
      top_archives: [],
    });
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('No data');
  });
});
