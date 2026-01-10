import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlBarChartComponent,
  AqlButtonComponent,
  AqlLineChartComponent,
  AqlDropdownComponent,
  AqlMenuItemComponent,
  AqlPieChartComponent,
  AqlPieChartItem,
} from 'aql-stylings';
import { QueryHistogramBucket, QueryMetadataResponse } from '../../models/search.model';
import type { EChartsOption, TooltipComponentFormatterCallbackParams } from 'echarts';

interface LabeledCount {
  label: string;
  count: number;
}

@Component({
  selector: 'app-query-overview-panel',
  standalone: true,
  imports: [
    CommonModule,
    TranslateModule,
    AqlButtonComponent,
    AqlDropdownComponent,
    AqlMenuItemComponent,
    AqlLineChartComponent,
    AqlBarChartComponent,
    AqlPieChartComponent,
  ],
  templateUrl: './query-overview-panel.component.html',
  styleUrl: './query-overview-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class QueryOverviewPanelComponent {
  readonly data = input<QueryMetadataResponse | null>(null);
  readonly query = input<string>('');
  readonly isLoading = input<boolean>(false);
  readonly interval = input<'day' | 'week' | 'month'>('month');
  readonly intervalChange = output<'day' | 'week' | 'month'>();
  readonly displayQuery = computed(() => {
    const responseQuery = this.data()?.query?.trim();
    if (responseQuery) {
      return responseQuery;
    }

    return this.query().trim();
  });
  readonly totalHits = computed<number | null>(() => {
    const total = this.data()?.total_hits;
    if (typeof total !== 'number' || Number.isNaN(total)) {
      return null;
    }

    return total;
  });
  readonly histogramBuckets = computed<QueryHistogramBucket[]>(() => {
    return this.data()?.date_histogram ?? [];
  });
  readonly hasHistogram = computed(() => this.histogramBuckets().length > 0);
  readonly histogramLabels = computed(() =>
    this.histogramBuckets().map(bucket => bucket.key_as_string),
  );
  readonly histogramCounts = computed(() => this.histogramBuckets().map(bucket => bucket.count));
  readonly topQueries = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_queries;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.key,
      count: typeof item.count === 'number' && !Number.isNaN(item.count) ? item.count : 0,
    }));
  });
  readonly topProviders = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_providers;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.domain,
      count: typeof item.count === 'number' && !Number.isNaN(item.count) ? item.count : 0,
    }));
  });
  readonly topArchives = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_archives;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.name,
      count: typeof item.count === 'number' && !Number.isNaN(item.count) ? item.count : 0,
    }));
  });
  readonly topQueryLabels = computed(() => this.topQueries().map(item => item.label));
  readonly topQueryCounts = computed(() => this.topQueries().map(item => item.count));
  readonly topProviderPieData = computed<AqlPieChartItem[]>(() =>
    this.topProviders().map(item => ({ name: item.label, value: item.count })),
  );
  readonly topArchivePieData = computed<AqlPieChartItem[]>(() =>
    this.topArchives().map(item => ({ name: item.label, value: item.count })),
  );
  readonly intervalLabel = computed(() => {
    const interval = this.interval();
    if (interval === 'day') return 'searchStats.intervalDay';
    if (interval === 'week') return 'searchStats.intervalWeek';
    return 'searchStats.intervalMonth';
  });
  readonly histogramChartOptions = computed<EChartsOption | null>(() => {
    const buckets = this.histogramBuckets();
    if (buckets.length === 0) {
      return null;
    }

    const labels = this.histogramLabels();
    const counts = this.histogramCounts();

    const firstDate = this.formatDate(labels[0]);
    const lastDate = this.formatDate(labels[labels.length - 1]);

    return {
      tooltip: {
        trigger: 'axis',
        formatter: (params: TooltipComponentFormatterCallbackParams) => {
          if (Array.isArray(params) && params.length > 0) {
            const dataIndex = params[0].dataIndex as number;
            const date = this.formatDate(labels[dataIndex]);
            const value = params[0].value;
            return `${date}<br/>Count: ${value}`;
          }
          return '';
        },
      },
      grid: {
        left: '4%',
        right: '4%',
        top: '6%',
        bottom: '15%',
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: labels,
        boundaryGap: false,
        axisLabel: {
          show: false,
        },
        axisTick: {
          show: false,
        },
        axisLine: {
          show: true,
        },
        axisPointer: {
          label: {
            formatter: (params: { value: string | number }) => {
              return this.formatDate(String(params.value));
            },
          } as Record<string, string | number | ((params: { value: string | number }) => string)>,
        },
      },
      graphic: [
        {
          type: 'text',
          left: 20,
          bottom: 10,
          style: {
            text: firstDate,
            fontSize: 11,
            fill: '#666',
          },
        },
        {
          type: 'text',
          right: 10,
          bottom: 10,
          style: {
            text: lastDate,
            fontSize: 11,
            fill: '#666',
            textAlign: 'right',
          },
        },
      ],
      yAxis: {
        type: 'value',
      },
      color: ['#3B82F6'],
      series: [
        {
          type: 'line',
          smooth: true,
          data: counts,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: '#3B82F6',
          },
          areaStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
                { offset: 1, color: 'rgba(59, 130, 246, 0.05)' },
              ],
            },
          },
        },
      ],
    } as EChartsOption;
  });

  onIntervalSelect(value: 'day' | 'week' | 'month'): void {
    if (value === this.interval()) {
      return;
    }

    this.intervalChange.emit(value);
  }

  private formatDate(dateString: string): string {
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) {
        return dateString;
      }

      const interval = this.interval();
      const options: Intl.DateTimeFormatOptions =
        interval === 'day'
          ? { year: 'numeric', month: 'short', day: 'numeric' }
          : interval === 'week'
            ? { year: 'numeric', month: 'short', day: 'numeric' }
            : { year: 'numeric', month: 'short' };

      return date.toLocaleDateString(undefined, options);
    } catch {
      return dateString;
    }
  }
}
