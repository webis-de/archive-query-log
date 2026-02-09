import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';

import { TranslateModule } from '@ngx-translate/core';
import { RelatedSerp, SearchResult } from '../../../models/search.model';
import { AqlPanelComponent } from 'aql-stylings';
import { LanguageService } from '../../../services/language.service';

@Component({
  selector: 'app-metadata-related-tab',
  standalone: true,
  imports: [TranslateModule, AqlPanelComponent],
  templateUrl: './metadata-related-tab.component.html',
  styleUrl: './metadata-related-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataRelatedTabComponent {
  readonly relatedSerps = input<RelatedSerp[]>([]);
  readonly isLoading = input<boolean>(false);
  readonly serpSelected = output<SearchResult>();

  private readonly languageService = inject(LanguageService);

  onRelatedSerpClick(serp: RelatedSerp): void {
    const searchResult: SearchResult = {
      _index: '',
      _type: '',
      _id: serp._id,
      _score: serp._score,
      _source: serp._source,
    };
    this.serpSelected.emit(searchResult);
  }

  formatDate(dateString: string): string {
    return this.languageService.formatDate(dateString);
  }
}
