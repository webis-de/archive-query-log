import { Directive, ElementRef, OnDestroy, effect, input, viewChild } from '@angular/core';
import * as echarts from 'echarts';

@Directive()
export abstract class BaseEChartComponent implements OnDestroy {
  readonly height = input<string>('220px');
  readonly colors = input<string[] | null>(null);
  readonly options = input<echarts.EChartsOption | null>(null);

  protected readonly chartContainer = viewChild<ElementRef<HTMLDivElement>>('chartContainer');
  protected chart: echarts.ECharts | null = null;

  private resizeObserver?: ResizeObserver;
  private resizeListener?: () => void;
  private initRetryTimeoutId: number | null = null;

  constructor() {
    effect(() => {
      const container = this.chartContainer();
      if (!container) return;
      this.ensureChart(container.nativeElement);
      this.applyOptions();
    });
  }

  ngOnDestroy(): void {
    if (this.initRetryTimeoutId !== null) {
      clearTimeout(this.initRetryTimeoutId);
      this.initRetryTimeoutId = null;
    }
    this.resizeObserver?.disconnect();
    if (this.resizeListener) {
      window.removeEventListener('resize', this.resizeListener);
    }
    this.chart?.dispose();
    this.chart = null;
  }

  protected abstract buildDefaultOption(): echarts.EChartsOption;

  private ensureChart(element: HTMLDivElement): void {
    if (this.chart) return;
    const width = element.clientWidth;
    const height = element.clientHeight;

    if (width === 0 || height === 0) {
      // Retry initialization when element has no dimensions
      if (this.initRetryTimeoutId !== null) {
        clearTimeout(this.initRetryTimeoutId);
      }
      this.initRetryTimeoutId = window.setTimeout(() => {
        if (!this.chart) {
          this.ensureChart(element);
        }
      }, 50);
      return;
    }

    this.chart = echarts.init(element, undefined, { renderer: 'canvas' });
    this.applyOptions();

    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => {
        this.chart?.resize();
      });
      this.resizeObserver.observe(element);
    } else {
      this.resizeListener = () => this.chart?.resize();
      window.addEventListener('resize', this.resizeListener);
    }
  }

  private applyOptions(): void {
    if (!this.chart) return;
    const option = this.options() ?? this.buildDefaultOption();
    this.chart.setOption(option, { notMerge: true, lazyUpdate: true });
  }
}
