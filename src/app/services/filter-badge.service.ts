import { Injectable, inject } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { FilterState } from '../models/filter.model';

@Injectable({
  providedIn: 'root',
})
export class FilterBadgeService {
  private readonly translate = inject(TranslateService);

  generateBadges(filters: FilterState): string[] {
    const badges: string[] = [];

    if (filters.dateFrom || filters.dateTo) {
      badges.push(this.formatDateBadge(filters.dateFrom, filters.dateTo));
    }

    if (filters.status && filters.status !== 'any') {
      const statusLabel = this.translate.instant('filter.badges.status');
      const statusValue = this.translate.instant(`filter.badges.${filters.status}`);
      badges.push(`${statusLabel}: ${statusValue}`);
    }

    if (filters.providers && filters.providers.length > 0) {
      const providerLabel = this.translate.instant('filter.badges.provider');
      filters.providers.forEach(p => badges.push(`${providerLabel}: ${p}`));
    }

    return badges.length === 0 ? [this.translate.instant('filter.badges.all')] : badges;
  }

  private formatDateBadge(dateFrom: string, dateTo: string): string {
    const dateLabel = this.translate.instant('filter.badges.date');
    const untilLabel = this.translate.instant('filter.badges.until');
    let dateStr = `${dateLabel}: `;

    if (dateFrom && dateTo) {
      dateStr += `${dateFrom} - ${dateTo}`;
    } else if (dateFrom) {
      dateStr += dateFrom;
    } else if (dateTo) {
      dateStr += `${untilLabel} ${dateTo}`;
    }

    return dateStr;
  }
}
