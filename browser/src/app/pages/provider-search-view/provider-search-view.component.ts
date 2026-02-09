import {
  Component,
  inject,
  signal,
  ChangeDetectionStrategy,
  computed,
  effect,
} from '@angular/core';
import { takeUntilDestroyed, toObservable, toSignal } from '@angular/core/rxjs-interop';

import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Location } from '@angular/common';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { combineLatest } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { ScrollingModule } from '@angular/cdk/scrolling';
import {
  createPanelNavigationController,
  PanelNavigationController,
} from '../../utils/panel-navigation';
import { ProviderService, ProviderDetail } from '../../services/provider.service';
import { SearchHeaderComponent } from '../../components/search-header/search-header.component';
import { SearchResultItemComponent } from '../../components/search-result-item/search-result-item.component';
import { ArchiveDetail } from '../../models/archive.model';
import { SearchResult } from '../../models/search.model';
import { AppQueryMetadataPanelComponent } from '../../components/query-metadata-panel/query-metadata-panel.component';

@Component({
  selector: 'app-provider-search-view',
  standalone: true,
  imports: [
    FormsModule,
    TranslateModule,
    SearchHeaderComponent,
    SearchResultItemComponent,
    SearchResultItemComponent,
    AppQueryMetadataPanelComponent,
    ScrollingModule
],
  templateUrl: './provider-search-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProviderSearchViewComponent {
  readonly providerService = inject(ProviderService);
  readonly route = inject(ActivatedRoute);
  readonly router = inject(Router);
  readonly location = inject(Location);
  readonly translate = inject(TranslateService);
  readonly providers = signal<ProviderDetail[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  readonly isPanelOpen = signal(false);
  readonly isTransitionEnabled = signal(false);
  readonly selectedProvider = signal<ProviderDetail | null>(null);
  readonly selectedProviderDetail = signal<ProviderDetail | null>(null);
  readonly isDetailLoading = signal<boolean>(false);
  readonly detailError = signal<string | null>(null);
  readonly searchQuery = signal('');
  readonly debouncedQuery = toSignal(
    toObservable(this.searchQuery).pipe(debounceTime(300), distinctUntilChanged()),
    { initialValue: '' },
  );
  readonly filteredProviders = computed(() => {
    const all = this.providers();
    const query = this.debouncedQuery();

    if (!query?.trim()) return all;

    const lower = query.toLowerCase();
    return all.filter(p => p.name.toLowerCase().includes(lower));
  });
  readonly totalCount = computed(() => this.filteredProviders().length);

  private readonly panelNavController: PanelNavigationController;

  constructor() {
    this.panelNavController = createPanelNavigationController({
      location: this.location,
      basePath: '/providers',
      getSearchQuery: () => this.searchQuery(),
      isPanelOpen: this.isPanelOpen,
    });

    // Enable transitions after initial render to prevent animation on page load
    setTimeout(() => this.isTransitionEnabled.set(true), 50);

    // Load all providers on init
    this.loadProviders();

    // Handle route params
    combineLatest([this.route.paramMap, this.route.queryParamMap])
      .pipe(takeUntilDestroyed())
      .subscribe(([params, queryParams]) => {
        const providerId = params.get('id');
        const query = queryParams.get('q');

        if (query !== null) {
          this.searchQuery.set(query);
          this.hasSearched.set(true);
        }

        if (providerId) {
          this.loadProviderDetail(providerId);
        }
      });

    effect(() => {
      const query = this.debouncedQuery();

      this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { q: query || null },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });
    });
  }

  onSearchInput(value: string): void {
    this.searchQuery.set(value);
    this.hasSearched.set(true);
  }

  onProviderClick(item: ProviderDetail | SearchResult | ArchiveDetail): void {
    const provider = item as ProviderDetail;
    this.selectedProvider.set(provider);
    this.loadProviderDetail(provider.id);
    this.panelNavController.navigateToItem(provider.id);
  }

  onClosePanel(): void {
    this.panelNavController.closePanel();
    setTimeout(() => {
      this.selectedProvider.set(null);
      this.selectedProviderDetail.set(null);
    }, 300);
  }

  trackByProviderId(index: number, item: ProviderDetail): string {
    return item.id;
  }

  private loadProviders(): void {
    this.isLoading.set(true);
    this.providerService
      .getProviders()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: providers => {
          this.providers.set(providers);
          this.isLoading.set(false);
          this.hasSearched.set(true);
        },
        error: () => {
          this.isLoading.set(false);
        },
      });
  }

  private loadProviderDetail(providerId: string): void {
    this.isDetailLoading.set(true);
    this.detailError.set(null);
    this.providerService.getProviderById(providerId).subscribe({
      next: detail => {
        this.selectedProviderDetail.set(detail);
        this.isDetailLoading.set(false);
        if (detail) {
          this.selectedProvider.set(detail);
          this.isPanelOpen.set(true);
        }
      },
      error: err => {
        this.isDetailLoading.set(false);
        this.detailError.set(this.translate.instant('providers.failedToLoadDetails'));
        console.error('Error loading provider details:', err);
      },
    });
  }
}
