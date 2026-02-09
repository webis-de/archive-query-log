import {
  Component,
  inject,
  signal,
  computed,
  ChangeDetectionStrategy,
  effect,
  Signal,
} from '@angular/core';
import { toObservable, toSignal } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { Router, ActivatedRoute } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { switchMap, map, catchError, startWith, of } from 'rxjs';
import { TranslateModule } from '@ngx-translate/core';
import { CompareService } from '../../services/compare.service';
import { SearchResult, CompareApiResponse, CompareResponse } from '../../models/search.model';
import { environment } from '../../../environments/environment';
import { AqlHeaderBarComponent, AqlPanelComponent, AqlButtonComponent } from 'aql-stylings';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-compare-page',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlPanelComponent,
    AqlButtonComponent,
    AqlHeaderBarComponent,
  ],
  templateUrl: './compare-page.component.html',
  styleUrl: './compare-page.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ComparePageComponent {
  readonly compareService = inject(CompareService);
  readonly sessionService = inject(SessionService);
  readonly isSidebarCollapsed = this.sessionService.sidebarCollapsed;
  readonly isPanelOpen = signal(false);
  readonly isTransitionEnabled = signal(true);
  readonly comparisonResource: Signal<{
    data: CompareResponse | null;
    loading: boolean;
    error: string | null;
  }>;
  readonly data: Signal<CompareResponse | null>;
  readonly loading: Signal<boolean>;
  readonly error: Signal<string | null>;
  readonly serpIds = this.compareService.selectedSerpIds;
  readonly hasRankings: Signal<boolean>;

  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private returnUrl?: string;

  constructor() {
    this.comparisonResource = toSignal(
      toObservable(this.compareService.selectedSerpIds).pipe(
        switchMap(ids => {
          if (ids.length < 2) return of({ data: null, loading: false, error: null });

          const idsParam = ids.join(',');
          return this.http
            .get<CompareApiResponse>(`${environment.apiUrl}/api/serps/compare`, {
              params: { ids: idsParam },
            })
            .pipe(
              map(response => ({
                data: this.compareService.mapApiResponse(response),
                loading: false,
                error: null,
              })),
              catchError(err => {
                console.error('Comparison error', err);
                return of({
                  data: null,
                  loading: false,
                  error: 'Failed to load comparison data.',
                });
              }),
              startWith({ data: null, loading: true, error: null }),
            );
        }),
      ),
      { initialValue: { data: null, loading: false, error: null } },
    );

    this.data = computed(() => this.comparisonResource().data);
    this.loading = computed(() => this.comparisonResource().loading);
    this.error = computed(() => this.comparisonResource().error);

    this.hasRankings = computed(() => {
      const data = this.data();
      return !!(data?.rankings && Object.keys(data.rankings).length > 0);
    });

    const nav = this.router.currentNavigation();
    if (nav?.extras?.state && 'returnUrl' in nav.extras.state) {
      this.returnUrl = nav.extras.state['returnUrl'];
    }

    const params = this.route.snapshot.paramMap;
    const urlIds = params.get('ids');
    if (urlIds) {
      const ids = urlIds.split(',').filter(id => id.length > 0);
      this.compareService.clear();
      ids.forEach(id => this.compareService.add(id));
    }

    effect(() => {
      const ids = this.compareService.selectedSerpIds();
      if (ids.length > 0) {
        const newUrl = `/serps/compare/${ids.join(',')}`;
        if (this.router.url.split('?')[0] !== newUrl) {
          this.router.navigateByUrl(newUrl, {
            replaceUrl: true,
            state: { returnUrl: this.returnUrl },
          });
        }
      }
    });
  }

  removeId(id: string): void {
    this.compareService.remove(id);
  }

  clearAll(): void {
    this.compareService.clear();
  }

  goBack(): void {
    if (this.returnUrl) {
      this.router.navigateByUrl(this.returnUrl);
    } else {
      this.router.navigate(['/']);
    }
  }

  getSerp(id: string): SearchResult | undefined {
    return this.data()?.serps[id];
  }

  getSerpLabel(id: string): string {
    const serp = this.getSerp(id);
    if (!serp) return id.substring(0, 8);
    return serp._source.provider?.domain || serp._source.url_query || id.substring(0, 8);
  }

  getStatusClass(code: number): string {
    if (code >= 200 && code < 300) return 'badge-success';
    if (code >= 300 && code < 400) return 'badge-info';
    if (code >= 400 && code < 500) return 'badge-warning';
    if (code >= 500) return 'badge-error';
    return 'badge-ghost';
  }
}
