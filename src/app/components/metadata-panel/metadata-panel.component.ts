import {
  Component,
  input,
  output,
  signal,
  computed,
  ChangeDetectionStrategy,
  inject,
  OnInit,
} from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { CommonModule } from '@angular/common';
import { TranslateModule, TranslateService } from '@ngx-translate/core';
import { AqlButtonComponent, AqlTabMenuComponent, TabItem } from 'aql-stylings';
import { SearchResult } from '../../models/search.model';
import { SessionService } from '../../services/session.service';

@Component({
  selector: 'app-metadata-panel',
  standalone: true,
  imports: [CommonModule, TranslateModule, AqlButtonComponent, AqlTabMenuComponent],
  templateUrl: './metadata-panel.component.html',
  styleUrl: './metadata-panel.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppMetadataPanelComponent implements OnInit {
  private readonly sessionService = inject(SessionService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly translate = inject(TranslateService);

  readonly isOpen = input.required<boolean>();
  readonly searchResult = input<SearchResult | null>(null);

  readonly closePanel = output<void>();

  readonly activeTab = signal<string>('text');

  readonly tabs = signal<TabItem[]>([]);

  ngOnInit(): void {
    this.updateTabLabels();
    this.translate.onLangChange.subscribe(() => {
      this.updateTabLabels();
    });
  }

  private updateTabLabels(): void {
    this.tabs.set([
      { id: 'text', label: this.translate.instant('metadata.textView'), icon: 'bi-file-text' },
      { id: 'html', label: this.translate.instant('metadata.htmlView'), icon: 'bi-code-square' },
      { id: 'website', label: this.translate.instant('metadata.website'), icon: 'bi-globe' },
      {
        id: 'metadata',
        label: this.translate.instant('metadata.metadata'),
        icon: 'bi-info-circle',
      },
    ]);
  }

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

  onClose(): void {
    this.closePanel.emit();
  }

  onTabChange(tabId: string): void {
    this.activeTab.set(tabId);
  }

  getSafeUrl(url: string): SafeResourceUrl {
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  }

  getExtractionText(): string {
    // Placeholder - will be replaced with actual extraction data
    return 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Vivamus lacinia odio vitae vestibulum vestibulum. Cras venenatis euismod malesuada. Nullam ac odio tempor orci dapibus ultrices in iaculis nunc.';
  }
}
