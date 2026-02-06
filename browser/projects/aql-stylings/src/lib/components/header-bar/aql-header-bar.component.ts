import { ChangeDetectionStrategy, Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'aql-header-bar',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-header-bar.component.html',
  styleUrl: './aql-header-bar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlHeaderBarComponent {}
