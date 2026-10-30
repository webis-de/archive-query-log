import { ChangeDetectionStrategy, Component, inject, input, output } from '@angular/core';

import { TranslateModule } from '@ngx-translate/core';
import { SearchResult } from '../../../models/search.model';
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
  readonly relatedSerps = input<SearchResult[]>([]);
  readonly isLoading = input<boolean>(false);
  readonly serpSelected = output<SearchResult>();

  private readonly languageService = inject(LanguageService);

  onRelatedSerpClick(serp: SearchResult): void {
    this.serpSelected.emit(serp);
  }

  formatDate(dateString: string): string {
    return this.languageService.formatDate(dateString);
  }
}
