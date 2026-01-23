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
  readonly legendPosition = input<'bottom' | 'left' | 'right'>('bottom');
  readonly legendOrient = input<'horizontal' | 'vertical' | null>(null);
  readonly showLabels = input<boolean>(true);
  readonly chartCenter = input<string[] | null>(null);
  readonly radius = input<string | string[]>(['35%', '70%']);

  protected buildDefaultOption(): echarts.EChartsOption {
    const position = this.legendPosition();
    const forcedOrient = this.legendOrient();
    const isHorizontal = forcedOrient ? forcedOrient === 'horizontal' : position === 'bottom';

    let defaultCenter = ['50%', '50%'];
    if (!this.chartCenter()) {
      if (position === 'bottom' && !isHorizontal) {
        // Vertical legend at bottom - move chart up
        defaultCenter = ['50%', '35%'];
      } else if (isHorizontal && position === 'bottom') {
        defaultCenter = ['50%', '45%'];
      } else if (position === 'left') {
        defaultCenter = ['60%', '50%'];
      } else if (position === 'right') {
        defaultCenter = ['40%', '50%'];
      }
    }

    return {
      color: this.colors() ?? undefined,
      tooltip: { trigger: 'item' },
      legend: {
        type: 'scroll',
        orient: isHorizontal ? 'horizontal' : 'vertical',
        [position]: 0,
        top: position === 'bottom' ? 'auto' : isHorizontal ? 'auto' : 'middle',
        left: isHorizontal ? 'center' : position === 'left' ? 0 : 'auto',
        right: position === 'right' ? 0 : 'auto',
      },
      series: [
        {
          type: 'pie',
          radius: this.radius(),
          center: this.chartCenter() ?? defaultCenter,
          data: this.data(),
          label: {
            show: this.showLabels(),
            formatter: '{d}%\n({c})',
          },
          labelLine: {
            show: this.showLabels(),
          },
        },
      ],
    };
  }
}
