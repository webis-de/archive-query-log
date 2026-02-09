import { Component, input, ChangeDetectionStrategy } from '@angular/core';

import { TranslateModule } from '@ngx-translate/core';
import { ArchiveDetail } from '../../../models/archive.model';

@Component({
  selector: 'app-metadata-archive-tab',
  standalone: true,
  imports: [TranslateModule],
  templateUrl: './metadata-archive-tab.component.html',
  styleUrl: './metadata-archive-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataArchiveTabComponent {
  readonly archiveDetail = input.required<ArchiveDetail | null>();
  readonly isLoading = input<boolean>(false);
}
