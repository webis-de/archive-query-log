import { ChangeDetectionStrategy, Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { ProviderDetail } from '../../../services/provider.service';

@Component({
  selector: 'app-provider-result-content',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './provider-result-content.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProviderResultContentComponent {
  readonly provider = input.required<ProviderDetail>();
  readonly domains = computed(() => {
    const prov = this.provider();
    return prov.domains;
  });
  readonly priority = computed(() => {
    const prov = this.provider();
    return prov.priority;
  });
}
