import {
  Component,
  input,
  signal,
  effect,
  inject,
  DestroyRef,
  computed,
  ChangeDetectionStrategy,
  Signal,
} from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import type { EChartsOption } from 'echarts';
import { ArchiveService } from '../../../services/archive.service';
import { ProviderService, ProviderDetail } from '../../../services/provider.service';
import {
  ArchiveStatistics,
  ProviderStatistics,
  TopEntityItem,
} from '../../../models/statistics.model';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { Observable } from 'rxjs';
import { AqlBarChartComponent, AqlKpiCardComponent } from 'aql-stylings';

@Component({
  selector: 'app-metadata-statistics-tab',
  standalone: true,
  imports: [DecimalPipe, TranslateModule, AqlBarChartComponent, AqlKpiCardComponent],
  templateUrl: './metadata-statistics-tab.component.html',
  styleUrl: './metadata-statistics-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataStatisticsTabComponent {
  readonly entityId = input.required<string>();
  readonly type = input.required<'archive' | 'provider'>();
  readonly isLoading = signal(false);
  readonly error = signal<string | null>(null);
  readonly statistics = signal<ArchiveStatistics | ProviderStatistics | null>(null);
  readonly isArchive = computed(() => this.type() === 'archive');
  readonly topEntities = computed<TopEntityItem[]>(() => {
    const stats = this.statistics();
    if (!stats) return [];

    return this.isArchive()
      ? ((stats as ArchiveStatistics).top_providers ?? [])
      : ((stats as ProviderStatistics).top_archives ?? []);
  });
  readonly hasTopEntities = computed(() => this.topEntities().length > 0);
  readonly chartOptions = computed<EChartsOption | null>(() => {
    const stats = this.statistics();
    if (!stats?.date_histogram?.length) return null;

    const dates = stats.date_histogram.map(item => item.date);
    const counts = stats.date_histogram.map(item => item.count);

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: unknown) => {
          const p = params as { name: string; value: number }[];
          const date = p[0]?.name ?? '';
          const count = p[0]?.value ?? 0;
          return `${date}<br/>Capture Count: <b>${new Intl.NumberFormat().format(count)}</b>`;
        },
      },
      grid: {
        top: '10%',
        bottom: '10%',
        left: '2%',
        right: '2%',
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLabel: { show: true },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        splitLine: {
          lineStyle: { color: '#e5e7eb' },
        },
      },
      series: [
        {
          data: counts,
          type: 'bar',
          itemStyle: { color: '#3B82F6' },
        },
      ],
    };
  });
  readonly providers: Signal<ProviderDetail[]>;
  readonly providerMap: Signal<Map<string, string>>;

  private readonly archiveService = inject(ArchiveService);
  private readonly providerService = inject(ProviderService);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    this.providers = toSignal(this.providerService.getProviders(), {
      initialValue: [] as ProviderDetail[],
    });

    this.providerMap = computed(() => {
      const map = new Map<string, string>();
      this.providers().forEach(p => map.set(p.id, p.name));
      return map;
    });

    effect(() => {
      const id = this.entityId();
      const type = this.type();
      if (id && type) {
        this.fetchStatistics(id, type);
      }
    });
  }

  getEntityName(item: TopEntityItem): string {
    if (item.provider) {
      return this.providerMap().get(item.provider) || item.provider;
    }
    return item.archive ?? 'Unknown';
  }

  private fetchStatistics(id: string, type: 'archive' | 'provider'): void {
    this.isLoading.set(true);
    this.error.set(null);
    this.statistics.set(null);

    const request$: Observable<ArchiveStatistics | ProviderStatistics> =
      type === 'archive'
        ? this.archiveService.getArchiveStatistics(id)
        : this.providerService.getProviderStatistics(id);

    request$.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: data => {
        this.statistics.set(data);
        this.isLoading.set(false);
      },
      error: (err: unknown) => {
        console.error('Failed to load statistics', err);
        this.error.set('Failed to load statistics.');
        this.isLoading.set(false);
      },
    });
  }
}
