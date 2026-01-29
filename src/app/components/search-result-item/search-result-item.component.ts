import { ChangeDetectionStrategy, Component, inject, input, output, computed } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlPanelComponent,
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlTooltipDirective,
} from 'aql-stylings';
import { SearchResult } from '../../models/search.model';
import { ProviderDetail } from '../../services/provider.service';
import { ArchiveDetail } from '../../models/archive.model';
import { LanguageService } from '../../services/language.service';
import { SerpResultContentComponent } from './serp-result-content/serp-result-content.component';
import { ProviderResultContentComponent } from './provider-result-content/provider-result-content.component';
import { ArchiveResultContentComponent } from './archive-result-content/archive-result-content.component';

export type ResultItem = SearchResult | ProviderDetail | ArchiveDetail;

@Component({
  selector: 'app-search-result-item',
  standalone: true,
  imports: [
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

  private readonly languageService = inject(LanguageService);

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
}
