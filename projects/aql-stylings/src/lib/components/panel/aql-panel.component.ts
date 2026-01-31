import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'aql-panel',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-panel.component.html',
  styleUrl: './aql-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlPanelComponent {
  readonly panelTitle = input<string | undefined>(undefined);
  readonly subtitle = input<string | undefined>(undefined);
  readonly bordered = input<boolean>(true);
  readonly shadow = input<boolean>(false);
  readonly rounded = input<boolean>(true);
  readonly isActive = input<boolean>(false);
  readonly hasFooter = input<boolean>(false);
}
