import { DecimalPipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlPanelComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlTooltipDirective,
} from 'aql-stylings';
import { SearchResult, Parser } from '../../models/search.model';
import { ProviderDetail } from '../../services/provider.service';
import { ArchiveDetail } from '../../models/archive.model';
import { LanguageService } from '../../services/language.service';
import { SerpResultContentComponent } from './serp-result-content/serp-result-content.component';
import { ProviderResultContentComponent } from './provider-result-content/provider-result-content.component';
import { ArchiveResultContentComponent } from './archive-result-content/archive-result-content.component';
import { CompareService } from '../../services/compare.service';

export type ResultItem = SearchResult | ProviderDetail | ArchiveDetail;
import { stripTrackingParams, hasTrackingParams } from '../../utils/url-sanitizer';

@Component({
  selector: 'app-search-result-item',
  standalone: true,
  imports: [
    CommonModule,
    DecimalPipe,
    TranslateModule,
    AqlPanelComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlTooltipDirective,
    SerpResultContentComponent,
    ProviderResultContentComponent,
    ArchiveResultContentComponent,
  ],
  templateUrl: './search-result-item.component.html',
  styleUrl: './search-result-item.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchResultItemComponent {
  readonly result = input<SearchResult | null>(null);
  readonly provider = input<ProviderDetail | null>(null);
  readonly archive = input<ArchiveDetail | null>(null);
  readonly isActive = input<boolean>(false);
  readonly clicked = output<ResultItem>();
  readonly panelTitle = computed(() => {
    const result = this.result();
    const provider = this.provider();
    const archive = this.archive();

    if (result) return result._source.url_query;
    if (provider) return provider.name;
    if (archive) return archive.name;
    return '';
  });
  readonly panelSubtitle = computed(() => {
    const result = this.result();
    const archive = this.archive();

    if (result) return result._source.capture.url;
    if (archive) return archive.id;
    return '';
  });
  readonly formattedDate = computed(() => {
    const res = this.result();
    return res ? this.languageService.formatDate(res._source.capture.timestamp) : '';
  });
  readonly compareService = inject(CompareService);
  isCompared = computed(() => {
    const result = this.result();
    return result ? this.compareService.isSelected(result._id) : false;
  });

  readonly hasTracking = computed<boolean>(() => {
    const res = this.result();
    const url = res ? res._source.capture.url : '';
    return hasTrackingParams(url);
  });

  readonly cleanUrl = computed<string>(() => {
    const res = this.result();
    const url = res ? res._source.capture.url : '';
    return stripTrackingParams(url);
  });

  readonly copyCleanSuccess = signal<boolean>(false);
  readonly copyOriginalSuccess = signal<boolean>(false);

  private readonly languageService = inject(LanguageService);

  toggleCompare(event: Event): void {
    event.stopPropagation();
    const result = this.result();
    if (result) {
      this.compareService.toggle(result._id);
    }
  }

  onClick(): void {
    const result = this.result();
    const provider = this.provider();
    const archive = this.archive();

    if (result) {
      this.clicked.emit(result);
    } else if (provider) {
      this.clicked.emit(provider);
    } else if (archive) {
      this.clicked.emit(archive);
    }
  }

  copyCleanUrl(event: Event): void {
    event.stopPropagation();
    const res = this.result();
    if (!res) return;
    const clean = this.cleanUrl();
    navigator.clipboard.writeText(clean).then(() => {
      this.copyCleanSuccess.set(true);
      setTimeout(() => this.copyCleanSuccess.set(false), 2000);
    });
  }

  copyOriginalUrl(event: Event): void {
    event.stopPropagation();
    const res = this.result();
    if (!res) return;
    const url = res._source.capture.url;
    navigator.clipboard.writeText(url).then(() => {
      this.copyOriginalSuccess.set(true);
      setTimeout(() => this.copyOriginalSuccess.set(false), 2000);
    });
  }

  getParserStatus(parser: Parser | undefined): 'success' | 'pending' | 'skipped' {
    if (!parser) return 'skipped';
    if (parser.last_parsed) return 'success';
    if (parser.should_parse) return 'pending';
    return 'skipped';
  }

  getFormattedUrlParams(): { key: string; value: string }[] {
    const res = this.result();
    if (!res) return [];
    try {
      const url = new URL(res._source.capture.url);
      const params: { key: string; value: string }[] = [];
      url.searchParams.forEach((value, key) => {
        if (params.length < 3) params.push({ key, value });
      });
      return params;
    } catch {
      return [];
    }
  }

  trackByKey(index: number, item: { key: string }): string {
    return item.key;
  }
}
