import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { UnfurlData } from '../../../models/search.model';

@Component({
  selector: 'app-metadata-unfurl-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './metadata-unfurl-tab.component.html',
  styleUrl: './metadata-unfurl-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataUnfurlTabComponent {
  readonly unfurlData = input<UnfurlData | null>(null);
  readonly unfurlWebUrl = input<string | null>(null);
  readonly isLoading = input<boolean>(false);
  readonly queryParamEntries = computed<{ key: string; value: string }[]>(() => {
    const unfurl = this.unfurlData();
    if (!unfurl?.query_parameters) return [];

    return Object.entries(unfurl.query_parameters).map(([key, value]) => ({
      key,
      value: Array.isArray(value) ? value.join(', ') : value,
    }));
  });
}
