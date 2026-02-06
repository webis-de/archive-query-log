import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { SearchResult } from '../../../models/search.model';
import { ProviderService, ProviderDetail } from '../../../services/provider.service';
import { AqlTooltipDirective, AqlButtonComponent } from 'aql-stylings';

@Component({
  selector: 'app-metadata-info-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule, AqlTooltipDirective, AqlButtonComponent],
  templateUrl: './metadata-info-tab.component.html',
  styleUrl: './metadata-info-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataInfoTabComponent {
  readonly searchResult = input<SearchResult | null>(null);
  readonly providerDetails = signal<ProviderDetail | null>(null);
  readonly isLoadingProvider = signal<boolean>(false);
  readonly providerError = signal<string | null>(null);
  readonly showProviderDetails = signal<boolean>(false);

  private lastLoadedProviderId = '';
  private readonly providerService = inject(ProviderService);

  toggleProviderDetails(): void {
    const result = this.searchResult();
    if (!result) return;

    const providerId = result._source.provider?.id;
    if (!providerId) return;

    this.showProviderDetails.update(v => !v);

    if (this.showProviderDetails() && providerId !== this.lastLoadedProviderId) {
      this.fetchProviderDetails(providerId);
    }
  }

  private fetchProviderDetails(providerId: string): void {
    this.isLoadingProvider.set(true);
    this.providerError.set(null);
    this.providerDetails.set(null);
    this.lastLoadedProviderId = providerId;

    this.providerService.getProviderById(providerId).subscribe({
      next: details => {
        this.providerDetails.set(details);
        this.isLoadingProvider.set(false);
      },
      error: err => {
        console.error('Failed to fetch provider details:', err);
        this.providerError.set('Failed to load provider details');
        this.isLoadingProvider.set(false);
      },
    });
  }
}
