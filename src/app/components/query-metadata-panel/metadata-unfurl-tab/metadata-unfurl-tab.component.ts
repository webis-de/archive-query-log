import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { AqlButtonComponent } from 'aql-stylings';
import { UnfurlData } from '../../../models/search.model';
import {
  stripTrackingParams,
  getTrackingParams,
  TRACKING_PARAMETERS,
} from '../../../utils/url-sanitizer';

@Component({
  selector: 'app-metadata-unfurl-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule, AqlButtonComponent],
  templateUrl: './metadata-unfurl-tab.component.html',
  styleUrl: './metadata-unfurl-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataUnfurlTabComponent {
  readonly unfurlData = input<UnfurlData | null>(null);
  readonly unfurlWebUrl = input<string | null>(null);
  readonly isLoading = input<boolean>(false);
  readonly originalUrl = input<string | null>(null);

  readonly copySuccess = signal<boolean>(false);

  readonly queryParamEntries = computed<{ key: string; value: string; isTracking: boolean }[]>(
    () => {
      const unfurl = this.unfurlData();
      if (!unfurl?.query_parameters) return [];

      return Object.entries(unfurl.query_parameters).map(([key, value]) => ({
        key,
        value: Array.isArray(value) ? value.join(', ') : value,
        isTracking: TRACKING_PARAMETERS.has(key.toLowerCase()),
      }));
    },
  );

  readonly trackingParamsFound = computed<string[]>(() => {
    const url = this.originalUrl();
    if (!url) return [];
    return getTrackingParams(url);
  });

  readonly hasTrackingParams = computed<boolean>(() => {
    return this.trackingParamsFound().length > 0;
  });

  readonly strippedUrl = computed<string | null>(() => {
    const url = this.originalUrl();
    if (!url || !this.hasTrackingParams()) return null;
    return stripTrackingParams(url);
  });

  copyStrippedUrl(): void {
    const stripped = this.strippedUrl();
    if (stripped) {
      navigator.clipboard.writeText(stripped).then(() => {
        this.copySuccess.set(true);
        setTimeout(() => this.copySuccess.set(false), 2000);
      });
    }
  }

  openStrippedUrl(): void {
    const stripped = this.strippedUrl();
    if (stripped) {
      window.open(stripped, '_blank', 'noopener,noreferrer');
    }
  }
}
