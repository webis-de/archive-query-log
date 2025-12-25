import {
  Component,
  input,
  output,
  signal,
  computed,
  ChangeDetectionStrategy,
  inject,
} from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { AqlButtonComponent, AqlTabMenuComponent, TabItem } from 'aql-stylings';
import { SearchResult } from '../../models/search.model';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-metadata-panel',
  standalone: true,
  imports: [CommonModule, AqlButtonComponent, AqlTabMenuComponent],
  templateUrl: './metadata-panel.component.html',
  styleUrl: './metadata-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppMetadataPanelComponent {
  private readonly sessionService = inject(SessionService);
  private readonly sanitizer = inject(DomSanitizer);

  readonly isOpen = input.required<boolean>();
  readonly searchResult = input<SearchResult | null>(null);

  readonly closePanel = output<void>();

  readonly activeTab = signal<string>('text');

  readonly tabs: TabItem[] = [
    { id: 'text', label: 'Text View', icon: 'bi-file-text' },
    { id: 'html', label: 'HTML View', icon: 'bi-code-square' },
    { id: 'website', label: 'Website', icon: 'bi-globe' },
    { id: 'metadata', label: 'Metadata', icon: 'bi-info-circle' },
  ];

  readonly panelClasses = computed(() => {
    const isSidebarCollapsed = this.sessionService.sidebarCollapsed();
    const widthClass = isSidebarCollapsed ? 'w-[60vw]' : 'w-[calc(60vw-20rem)]';

    const classes = [
      'h-full',
      widthClass,
      'bg-base-100',
      'border-l',
      'border-base-300',
      'flex',
      'flex-col',
      'flex-shrink-0',
      'transition-[width]',
      'duration-300',
    ];

    return classes.join(' ');
  });

  /**
   * Computed raw memento URL string for use in links
   */
  readonly mementoUrlString = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const mementoApiUrl = result._source.archive?.memento_api_url;
    const timestamp = result._source.capture.timestamp;
    const captureUrl = result._source.capture.url;

    if (!mementoApiUrl || !timestamp || !captureUrl) {
      return captureUrl || '';
    }

    const formattedTimestamp = this.formatTimestampForMemento(timestamp);
    return `${mementoApiUrl}/${formattedTimestamp}/${captureUrl}`;
  });

  /**
   * Computed memento URL - only recalculates when searchResult changes
   */
  readonly mementoUrl = computed<SafeResourceUrl | null>(() => {
    const urlString = this.mementoUrlString();
    if (!urlString) return null;
    return this.sanitizer.bypassSecurityTrustResourceUrl(urlString);
  });

  /**
   * Computed archive date for display - only recalculates when searchResult changes
   */
  readonly archiveDate = computed<string>(() => {
    const result = this.searchResult();
    if (!result) return '';

    const timestamp = result._source.capture.timestamp;
    if (!timestamp) return '';

    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return '';

      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short',
      });
    } catch {
      return '';
    }
  });

  onClose(): void {
    this.closePanel.emit();
  }

  onTabChange(tabId: string): void {
    this.activeTab.set(tabId);
  }

  /**
   * Formats an ISO timestamp to the memento format (YYYYMMDDHHmmss)
   * @param isoTimestamp ISO 8601 timestamp string
   * @returns Formatted timestamp string for memento URL
   */
  formatTimestampForMemento(isoTimestamp: string): string {
    try {
      const date = new Date(isoTimestamp);
      if (isNaN(date.getTime())) {
        return '';
      }

      const year = date.getUTCFullYear();
      const month = String(date.getUTCMonth() + 1).padStart(2, '0');
      const day = String(date.getUTCDate()).padStart(2, '0');
      const hours = String(date.getUTCHours()).padStart(2, '0');
      const minutes = String(date.getUTCMinutes()).padStart(2, '0');
      const seconds = String(date.getUTCSeconds()).padStart(2, '0');

      return `${year}${month}${day}${hours}${minutes}${seconds}`;
    } catch {
      return '';
    }
  }

  getExtractionText(): string {
    // Placeholder - will be replaced with actual extraction data
    return 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus lacinia odio vitae vestibulum vestibulum. Cras venenatis euismod malesuada. Nullam ac odio tempor orci dapibus ultrices in iaculis nunc.';
  }
}
