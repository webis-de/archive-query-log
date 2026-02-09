import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import { AqlPanelComponent, AqlInputFieldComponent } from 'aql-stylings';
import { UnbrandedSerp } from '../../../models/search.model';

@Component({
  selector: 'app-metadata-unbranded-tab',
  standalone: true,
  imports: [FormsModule, TranslateModule, AqlPanelComponent, AqlInputFieldComponent],
  templateUrl: './metadata-unbranded-tab.component.html',
  styleUrl: './metadata-unbranded-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataUnbrandedTabComponent {
  readonly unbranded = input<UnbrandedSerp | null>(null);
  readonly isLoading = input<boolean>(false);
}
