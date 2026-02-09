import { Component, input, ChangeDetectionStrategy } from '@angular/core';

import { TranslateModule } from '@ngx-translate/core';
import { ProviderDetail } from '../../../services/provider.service';

@Component({
  selector: 'app-metadata-provider-tab',
  standalone: true,
  imports: [TranslateModule],
  templateUrl: './metadata-provider-tab.component.html',
  styleUrl: './metadata-provider-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataProviderTabComponent {
  readonly providerDetail = input.required<ProviderDetail | null>();
  readonly isLoading = input<boolean>(false);
}
