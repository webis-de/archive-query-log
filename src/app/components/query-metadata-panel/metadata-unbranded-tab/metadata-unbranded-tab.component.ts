import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { AqlPanelComponent } from 'aql-stylings';
import { UnbrandedSerp } from '../../../models/search.model';

@Component({
  selector: 'app-metadata-unbranded-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule, AqlPanelComponent],
  templateUrl: './metadata-unbranded-tab.component.html',
  styleUrl: './metadata-unbranded-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataUnbrandedTabComponent {
  readonly unbranded = input<UnbrandedSerp | null>(null);
  readonly isLoading = input<boolean>(false);
}
