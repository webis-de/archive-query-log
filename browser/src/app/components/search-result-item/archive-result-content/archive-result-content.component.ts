import { ChangeDetectionStrategy, Component, input, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { ArchiveDetail } from '../../../models/archive.model';

@Component({
  selector: 'app-archive-result-content',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './archive-result-content.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ArchiveResultContentComponent {
  readonly archive = input.required<ArchiveDetail>();
  readonly cdxApiUrl = computed(() => {
    const arch = this.archive();
    return arch.cdx_api_url;
  });
  readonly serpCount = computed(() => {
    const arch = this.archive();
    return arch.serp_count;
  });
}
