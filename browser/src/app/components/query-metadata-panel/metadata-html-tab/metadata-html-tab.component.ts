import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { SearchResult } from '../../../models/search.model';

@Component({
  selector: 'app-metadata-html-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './metadata-html-tab.component.html',
  styleUrl: './metadata-html-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataHtmlTabComponent {
  readonly searchResult = input<SearchResult | null>(null);
}
