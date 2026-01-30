import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  output,
  signal,
  viewChild,
  WritableSignal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { LanguageService } from '../../services/language.service';
import {
  AqlBarChartComponent,
  AqlButtonComponent,
  AqlInputFieldComponent,
  AqlLineChartComponent,
  AqlDropdownComponent,
  AqlMenuItemComponent,
  AqlPieChartComponent,
  AqlPieChartItem,
  AqlScrollbarDirective,
  BaseEChartComponent,
} from 'aql-stylings';
import { QueryHistogramBucket, QueryMetadataResponse } from '../../models/search.model';
import { ExportService } from '../../services/export.service';
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
    FormsModule,
    TranslateModule,
    AqlButtonComponent,
    AqlInputFieldComponent,
    AqlDropdownComponent,
    AqlMenuItemComponent,
    AqlLineChartComponent,
    AqlBarChartComponent,
    AqlPieChartComponent,
    AqlScrollbarDirective,
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
  // Emit when user clicks a histogram bucket: { from_timestamp, to_timestamp }
  readonly histogramClick = output<{
    from_timestamp: string;
    to_timestamp: string;
  }>();

  readonly showTopQueriesList = signal<boolean>(false);
  readonly showTopProvidersList = signal<boolean>(false);
  readonly showTopArchivesList = signal<boolean>(false);
  readonly topQueriesCopied = signal(false);
  readonly topProvidersCopied = signal(false);
  readonly topArchivesCopied = signal(false);
  readonly topQueryBarChart = viewChild<AqlBarChartComponent>('topQueryBarChart');
  readonly topProviderPieChart = viewChild<AqlPieChartComponent>('topProviderPieChart');
  readonly topArchivePieChart = viewChild<AqlPieChartComponent>('topArchivePieChart');
  readonly histogramChart = viewChild<AqlLineChartComponent>('histogramChart');
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
  readonly histogramLabels = computed(() => this.histogramBuckets().map(bucket => bucket.date));
  readonly histogramCounts = computed(() => this.histogramBuckets().map(bucket => bucket.count));
  readonly topQueries = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_queries;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.query,
      count: typeof item.count === 'number' && !Number.isNaN(item.count) ? item.count : 0,
    }));
  });
  readonly topProviders = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_providers;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.provider,
      count: typeof item.count === 'number' && !Number.isNaN(item.count) ? item.count : 0,
    }));
  });
  readonly topArchives = computed<LabeledCount[]>(() => {
    const items = this.data()?.top_archives;
    if (!items?.length) return [];
    return items.map(item => ({
      label: item.archive,
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
            const date = this.languageService.formatDateTime(labels[dataIndex]);
            const value = params[0].value;
            const hint = this.translate.instant('searchStats.clickToFilter');
            return `${date}<br/>Count: ${value}<br/><span style="font-size:11px;color:#888">${hint}</span>`;
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
              return this.languageService.formatDateTime(String(params.value));
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
        {
          type: 'bar',
          data: counts,
          barWidth: '80%',
          itemStyle: {
            color: 'transparent',
          },
          emphasis: {
            itemStyle: {
              color: 'rgba(59,130,246,0.06)',
            },
          },
          silent: false,
          z: 5,
          cursor: 'pointer',
        },
      ],
    } as EChartsOption;
  });

  private readonly exportService = inject(ExportService);
  private readonly translate = inject(TranslateService);
  private readonly languageService = inject(LanguageService);

  onIntervalSelect(value: 'day' | 'week' | 'month'): void {
    if (value === this.interval()) {
      return;
    }

    this.intervalChange.emit(value);
  }

  getFilename(suffix: string): string {
    const query = this.displayQuery() || 'unknown';
    const sanitizedQuery = query.replace(/[^a-z0-9.-]/gi, '_').toLowerCase();
    return `query_${sanitizedQuery}_${suffix}`;
  }

  copyDataToClipboard(data: LabeledCount[], feedbackSignal: WritableSignal<boolean>): void {
    const formattedData = data.map(item => ({ Label: item.label, Count: item.count }));
    const text = this.exportService.formatAsTsv(formattedData, ['Label', 'Count']);
    this.exportService.copyToClipboard(text).subscribe(() => {
      feedbackSignal.set(true);
      setTimeout(() => feedbackSignal.set(false), 5000);
    });
  }

  downloadDataAsCsv(data: LabeledCount[], filename: string): void {
    const formattedData = data.map(item => ({ Label: item.label, Count: item.count }));
    this.exportService.downloadCsv(formattedData, filename, { headers: ['Label', 'Count'] });
  }

  downloadChartAsPng(chart: BaseEChartComponent | undefined, filename: string): void {
    if (!chart) return;
    const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
    if (url) {
      this.exportService.downloadUrl(url, filename);
    }
  }

  onHistogramClick(params: unknown): void {
    // echarts click payload includes dataIndex and name
    try {
      const dataIndex = (params as { dataIndex?: number } | undefined)?.dataIndex;
      if (dataIndex === undefined || dataIndex === null) return;
      const label = this.histogramLabels()[dataIndex];
      if (!label) return;

      const interval = this.interval();
      const range = this.computeRangeForLabel(label, interval);

      this.histogramClick.emit({
        from_timestamp: range.from,
        to_timestamp: range.to,
      });
    } catch {
      // ignore errors
    }
  }

  private computeRangeForLabel(label: string, interval: 'day' | 'week' | 'month') {
    const date = new Date(label);
    if (isNaN(date.getTime())) {
      // fallback: treat label as exact date
      const d = new Date(label);
      return { from: d.toISOString(), to: d.toISOString() };
    }

    const start = new Date(
      Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 0, 0, 0),
    );
    let end: Date;

    if (interval === 'day') {
      end = new Date(start);
      end.setUTCDate(end.getUTCDate() + 1);
      end.setUTCMilliseconds(end.getUTCMilliseconds() - 1);
    } else if (interval === 'week') {
      // Assuming label is start of week
      end = new Date(start);
      end.setUTCDate(end.getUTCDate() + 7);
      end.setUTCMilliseconds(end.getUTCMilliseconds() - 1);
    } else {
      // month
      end = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1));
      end.setUTCMilliseconds(end.getUTCMilliseconds() - 1);
    }

    return { from: start.toISOString(), to: end.toISOString() };
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
