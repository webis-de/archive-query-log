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
import { ArchiveService } from '../../services/archive.service';
import { ArchiveDetail } from '../../models/archive.model';
import { SearchHeaderComponent } from '../../components/search-header/search-header.component';
import { SearchResultItemComponent } from '../../components/search-result-item/search-result-item.component';
import { ProviderDetail } from '../../services/provider.service';
import { SearchResult } from '../../models/search.model';
import { AppQueryMetadataPanelComponent } from '../../components/query-metadata-panel/query-metadata-panel.component';

@Component({
  selector: 'app-archive-search-view',
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
  templateUrl: './archive-search-view.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArchiveSearchViewComponent {
  readonly archiveService = inject(ArchiveService);
  readonly route = inject(ActivatedRoute);
  readonly router = inject(Router);
  readonly location = inject(Location);
  readonly translate = inject(TranslateService);
  readonly archives = signal<ArchiveDetail[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  readonly isPanelOpen = signal(false);
  readonly isTransitionEnabled = signal(false);
  readonly selectedArchive = signal<ArchiveDetail | null>(null);
  readonly selectedArchiveDetail = signal<ArchiveDetail | null>(null);
  readonly isDetailLoading = signal<boolean>(false);
  readonly detailError = signal<string | null>(null);
  readonly searchQuery = signal('');
  readonly debouncedQuery = toSignal(
    toObservable(this.searchQuery).pipe(debounceTime(300), distinctUntilChanged()),
    { initialValue: '' },
  );
  readonly filteredArchives = computed(() => {
    const all = this.archives();
    const query = this.debouncedQuery();

    if (!query?.trim()) return all;

    const lower = query.toLowerCase();
    return all.filter(a => a.name.toLowerCase().includes(lower));
  });
  readonly totalCount = computed(() => this.filteredArchives().length);

  private readonly panelNavController: PanelNavigationController;

  constructor() {
    this.panelNavController = createPanelNavigationController({
      location: this.location,
      basePath: '/archives',
      getSearchQuery: () => this.searchQuery(),
      isPanelOpen: this.isPanelOpen,
    });

    setTimeout(() => this.isTransitionEnabled.set(true), 50);

    this.loadArchives();

    // Handle route params
    combineLatest([this.route.paramMap, this.route.queryParamMap])
      .pipe(takeUntilDestroyed())
      .subscribe(([params, queryParams]) => {
        const archiveId = params.get('id');
        const query = queryParams.get('q');

        if (query !== null) {
          this.searchQuery.set(query);
          this.hasSearched.set(true);
        }

        if (archiveId) {
          this.loadArchiveDetail(archiveId);
        }
      });

    // Effect to update URL when debounced query changes
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

  onArchiveClick(item: ArchiveDetail | SearchResult | ProviderDetail): void {
    const archive = item as ArchiveDetail;
    this.selectedArchive.set(archive);
    this.loadArchiveDetail(archive.id);
    this.panelNavController.navigateToItem(archive.id);
  }

  onClosePanel(): void {
    this.panelNavController.closePanel();
    setTimeout(() => {
      this.selectedArchive.set(null);
      this.selectedArchiveDetail.set(null);
    }, 300);
  }

  trackByArchiveId(index: number, item: ArchiveDetail): string {
    return item.id;
  }

  private loadArchives(): void {
    this.isLoading.set(true);
    this.archiveService
      .getArchives()
      .pipe(takeUntilDestroyed())
      .subscribe({
        next: archives => {
          this.archives.set(archives);
          this.isLoading.set(false);
          this.hasSearched.set(true);
        },
        error: () => {
          this.isLoading.set(false);
        },
      });
  }

  private loadArchiveDetail(archiveId: string): void {
    this.isDetailLoading.set(true);
    this.detailError.set(null);
    this.archiveService.getArchiveById(archiveId).subscribe({
      next: detail => {
        this.selectedArchiveDetail.set(detail);
        this.isDetailLoading.set(false);
        if (detail) {
          this.selectedArchive.set({ id: detail.id, name: detail.name });
          this.isPanelOpen.set(true);
        }
      },
      error: err => {
        this.isDetailLoading.set(false);
        this.detailError.set(this.translate.instant('archives.failedToLoadDetails'));
        console.error('Error loading archive details:', err);
      },
    });
  }
}
