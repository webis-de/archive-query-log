import { ComponentFixture, TestBed } from '@angular/core/testing';
import { TranslateModule } from '@ngx-translate/core';
import { AppRelatedSerpCardComponent } from './related-serp-card.component';
import { RelatedSerp } from '../../models/search.model';

describe('AppRelatedSerpCardComponent', () => {
  let component: AppRelatedSerpCardComponent;
  let fixture: ComponentFixture<AppRelatedSerpCardComponent>;

  const mockSerp: RelatedSerp = {
    _id: 'test-id-123',
    _score: 1.5,
    _source: {
      last_modified: '2024-01-15T10:30:00Z',
      provider: {
        id: 'google',
        domain: 'google.com',
        url_path_prefix: '/search',
        priority: 1,
      },
      capture: {
        id: 'capture-123',
        url: 'https://google.com/search?q=test',
        timestamp: '2024-01-15T10:30:00Z',
        status_code: 200,
        digest: 'abc123',
        mimetype: 'text/html',
      },
      url_query: 'test query',
      url_query_parser: { should_parse: true },
      url_page_parser: { should_parse: true },
      url_offset_parser: { should_parse: true },
      warc_query_parser: { should_parse: true },
      warc_snippets_parser: { should_parse: true },
    },
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppRelatedSerpCardComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(AppRelatedSerpCardComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('serp', mockSerp);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should display the query', () => {
    const compiled = fixture.nativeElement;
    expect(compiled.textContent).toContain('test query');
  });

  it('should display the provider domain', () => {
    const compiled = fixture.nativeElement;
    expect(compiled.textContent).toContain('google.com');
  });

  it('should emit serpClick event when clicked', () => {
    spyOn(component.serpClick, 'emit');
    component.onClick();
    expect(component.serpClick.emit).toHaveBeenCalledWith(mockSerp);
  });

  it('should format timestamp correctly', () => {
    const result = component.formatTimestamp('2024-01-15T10:30:00Z');
    expect(result).toContain('2024');
    expect(result).toContain('Jan');
    expect(result).toContain('15');
  });

  it('should return original timestamp if invalid', () => {
    const invalidTimestamp = 'invalid-date';
    const result = component.formatTimestamp(invalidTimestamp);
    expect(result).toBe(invalidTimestamp);
  });
});
