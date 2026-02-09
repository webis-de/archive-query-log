import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import * as echarts from 'echarts';
import { BaseEChartComponent } from '../base/base-echart.component';

@Component({
  selector: 'aql-bar-chart',
  standalone: true,
  imports: [],
  templateUrl: './aql-bar-chart.component.html',
  styleUrl: './aql-bar-chart.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlBarChartComponent extends BaseEChartComponent {
  readonly data = input<number[]>([]);
  readonly labels = input<string[]>([]);

  protected buildDefaultOption(): echarts.EChartsOption {
    const labels = this.labels();
    const data = this.data();
    const resolvedLabels = labels.length ? labels : data.map((_, index) => `${index + 1}`);

    return {
      color: this.colors() ?? undefined,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '4%', right: '4%', top: '12%', bottom: '6%', containLabel: true },
      xAxis: { type: 'category', data: resolvedLabels },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'bar',
          data,
          barCategoryGap: '2%',
          label: {
            show: true,
            position: 'top',
          },
        },
      ],
    };
  }
}
