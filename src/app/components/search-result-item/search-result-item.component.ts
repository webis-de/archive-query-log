import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlPanelComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlTooltipDirective,
} from 'aql-stylings';
import { SearchResult, Parser } from '../../models/search.model';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'app-search-result-item',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlPanelComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlTooltipDirective,
  ],
  templateUrl: './search-result-item.component.html',
  styleUrl: './search-result-item.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchResultItemComponent {
  readonly result = input.required<SearchResult>();
  readonly clicked = output<SearchResult>();

  private readonly languageService = inject(LanguageService);

  onClick(): void {
    this.clicked.emit(this.result());
  }

  formatDate(dateString: string): string {
    return this.languageService.formatDate(dateString);
  }

  getStatusColorClass(code: number): string {
    if (code >= 200 && code < 300) return 'text-success';
    if (code >= 300 && code < 400) return 'text-info';
    if (code >= 400 && code < 500) return 'text-warning';
    if (code >= 500) return 'text-error';
    return 'text-base-content/60';
  }

  getParserStatus(parser: Parser): 'success' | 'pending' | 'skipped' {
    if (parser.last_parsed) return 'success';
    if (parser.should_parse) return 'pending';
    return 'skipped';
  }

  getFormattedUrlParams(): { key: string; value: string }[] {
    try {
      const url = new URL(this.result()._source.capture.url);
      const params: { key: string; value: string }[] = [];
      url.searchParams.forEach((value, key) => {
        if (params.length < 3) {
          params.push({ key, value });
        }
      });
      return params;
    } catch {
      return [];
    }
  }
}
