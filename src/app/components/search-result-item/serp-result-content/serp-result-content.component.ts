import { ChangeDetectionStrategy, Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { SearchResult, Parser } from '../../../models/search.model';

@Component({
  selector: 'app-serp-result-content',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './serp-result-content.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SerpResultContentComponent {
  readonly result = input.required<SearchResult>();
  readonly formattedUrlParams = computed<{ key: string; value: string }[]>(() => {
    const result = this.result();
    try {
      const url = new URL(result._source.capture.url);
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
  });

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
}
