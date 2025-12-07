import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
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
  @Input() panelTitle?: string;
  @Input() subtitle?: string;
  @Input() bordered = true;
  @Input() shadow = false;
  @Input() rounded = true;
}
