import { Component, input, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { ArchiveDetail } from '../../../models/archive.model';

@Component({
  selector: 'app-metadata-archive-tab',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './metadata-archive-tab.component.html',
  styleUrl: './metadata-archive-tab.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MetadataArchiveTabComponent {
  readonly archiveDetail = input.required<ArchiveDetail | null>();
  readonly isLoading = input<boolean>(false);
}
