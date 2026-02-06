import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SerpResultContentComponent } from './serp-result-content.component';
import { TranslateModule } from '@ngx-translate/core';
import { SearchResult } from '../../../models/search.model';

describe('SerpResultContentComponent', () => {
  let component: SerpResultContentComponent;
  let fixture: ComponentFixture<SerpResultContentComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SerpResultContentComponent, TranslateModule.forRoot()],
    }).compileComponents();

    fixture = TestBed.createComponent(SerpResultContentComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('result', {
      _id: '1',
      _source: {
        capture: {
          url: 'http://test.com',
          timestamp: '2022',
          status_code: 200,
          mimetype: 'text/html',
        },
        url_query_parser: {},
        url_page_parser: {},
        warc_query_parser: {},
      },
    } as SearchResult);
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
