import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SearchResultItemComponent } from './search-result-item.component';
import { TranslateModule } from '@ngx-translate/core';
import { LanguageService } from '../../services/language.service';
import { SearchResult, SearchResultSource } from '../../models/search.model';

describe('SearchResultItemComponent', () => {
  let component: SearchResultItemComponent;
  let fixture: ComponentFixture<SearchResultItemComponent>;

  const mockSearchResult: SearchResult = {
    _index: 'test_index',
    _type: 'test_type',
    _id: 'test_id',
    _score: 1.0,
    _source: {
      url_query: 'test query',
      capture: {
        url: 'http://test.com',
        timestamp: '2023-01-01T00:00:00Z',
        mimetype: 'text/html',
        status_code: 200,
      },
      provider: {
        domain: 'test.com',
      },
      url_query_parser: { should_parse: true, last_parsed: '2023-01-01T00:00:00Z' },
      url_page_parser: { should_parse: true, last_parsed: '2023-01-01T00:00:00Z' },
      warc_query_parser: { should_parse: false },
    } as unknown as SearchResultSource,
  };

  const mockLanguageService = {
    formatDate: (date: string) => date,
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SearchResultItemComponent, TranslateModule.forRoot()],
      providers: [{ provide: LanguageService, useValue: mockLanguageService }],
    }).compileComponents();

    fixture = TestBed.createComponent(SearchResultItemComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('result', mockSearchResult);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should emit clicked event when onClick is called', () => {
    spyOn(component.clicked, 'emit');
    component.onClick();
    expect(component.clicked.emit).toHaveBeenCalledWith(mockSearchResult);
  });
});
