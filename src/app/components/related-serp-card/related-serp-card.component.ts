import { Component, input, output, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { RelatedSerp } from '../../models/search.model';

@Component({
  selector: 'app-related-serp-card',
  standalone: true,
  imports: [CommonModule, TranslateModule],
  templateUrl: './related-serp-card.component.html',
  styleUrl: './related-serp-card.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AppRelatedSerpCardComponent {
  readonly serp = input.required<RelatedSerp>();

  readonly serpClick = output<RelatedSerp>();

  onClick(): void {
    this.serpClick.emit(this.serp());
  }

  /**
   * Format timestamp for display
   */
  formatTimestamp(timestamp: string): string {
    try {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return timestamp;

      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return timestamp;
    }
  }
}
