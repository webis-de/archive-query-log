import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import * as echarts from 'echarts';
import { BaseEChartComponent } from '../base/base-echart.component';

export interface AqlPieChartItem {
  name: string;
  value: number;
}

@Component({
  selector: 'aql-pie-chart',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-pie-chart.component.html',
  styleUrl: './aql-pie-chart.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlPieChartComponent extends BaseEChartComponent {
  readonly data = input<AqlPieChartItem[]>([]);

  protected buildDefaultOption(): echarts.EChartsOption {
    return {
      color: this.colors() ?? undefined,
      tooltip: { trigger: 'item' },
      legend: { type: 'scroll', bottom: 0 },
      series: [
        {
          type: 'pie',
          radius: ['35%', '70%'],
          center: ['50%', '45%'],
          data: this.data(),
          label: { formatter: '{b}: {d}%' },
        },
      ],
    };
  }
}
