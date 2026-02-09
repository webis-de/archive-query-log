import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import * as echarts from 'echarts';
import { BaseEChartComponent } from '../base/base-echart.component';

@Component({
  selector: 'aql-line-chart',
  standalone: true,
  imports: [],
  templateUrl: './aql-line-chart.component.html',
  styleUrl: './aql-line-chart.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlLineChartComponent extends BaseEChartComponent {
  readonly data = input<number[]>([]);
  readonly labels = input<string[]>([]);
  readonly smooth = input<boolean>(true);
  readonly showArea = input<boolean>(false);

  protected buildDefaultOption(): echarts.EChartsOption {
    const labels = this.labels();
    const data = this.data();
    const resolvedLabels = labels.length ? labels : data.map((_, index) => `${index + 1}`);
    const series: echarts.SeriesOption = {
      type: 'line',
      smooth: this.smooth(),
      data,
      showSymbol: false,
    };

    if (this.showArea()) {
      (series as echarts.LineSeriesOption).areaStyle = {};
    }

    return {
      color: this.colors() ?? undefined,
      tooltip: { trigger: 'axis' },
      grid: { left: '4%', right: '4%', top: '6%', bottom: '6%', containLabel: true },
      xAxis: { type: 'category', data: resolvedLabels, boundaryGap: false },
      yAxis: { type: 'value' },
      series: [series],
    };
  }
}
