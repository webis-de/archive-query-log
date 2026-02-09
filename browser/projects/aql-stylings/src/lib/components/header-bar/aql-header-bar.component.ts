import { ChangeDetectionStrategy, Component } from '@angular/core';


@Component({
  selector: 'aql-header-bar',
  standalone: true,
  imports: [],
  templateUrl: './aql-header-bar.component.html',
  styleUrl: './aql-header-bar.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlHeaderBarComponent {}
