import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';

export type KpiColorScheme =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'info'
  | 'success'
  | 'warning'
  | 'error'
  | 'neutral';

@Component({
  selector: 'aql-kpi-card',
  standalone: true,
  imports: [DecimalPipe],
  templateUrl: './aql-kpi-card.component.html',
  styleUrl: './aql-kpi-card.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlKpiCardComponent {
  readonly title = input.required<string>();
  readonly value = input.required<string | number>();
  readonly subtitle = input<string>();
  readonly secondary = input<string>();
  readonly icon = input<string>();
  readonly colorScheme = input<KpiColorScheme>('primary');
  readonly formatAsNumber = input<boolean>(true);
  readonly compact = input<boolean>(false);
  readonly valueColorClass = computed(() => `text-${this.colorScheme()}`);
  readonly formattedValue = computed(() => {
    const val = this.value();
    if (!this.formatAsNumber() || typeof val === 'string') {
      return val;
    }
    return val;
  });
}
