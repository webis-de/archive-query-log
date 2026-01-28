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
      const statusLabel = this.translate.instant('filter.badges.status') as string;
      const statusValue = this.translate.instant(`filter.${filters.status}`) as string;
      badges.push(`${statusLabel}: ${statusValue}`);
    }

    if (filters.providers && filters.providers.length > 0) {
      const providerLabel = this.translate.instant('filter.badges.provider') as string;
      filters.providers.forEach(p => badges.push(`${providerLabel}: ${p}`));
    }

    if (filters.advancedMode) {
      badges.push(this.translate.instant('filter.badges.advancedSearch') as string);
    }

    if (filters.fuzzy) {
      const fuzzyLabel = this.translate.instant('filter.badges.fuzzySearch') as string;
      const fuzziness = filters.fuzziness || 'AUTO';
      badges.push(`${fuzzyLabel} (${fuzziness})`);
    }

    if (filters.expandSynonyms) {
      badges.push(this.translate.instant('filter.badges.expandSynonyms') as string);
    }

    return badges.length === 0 ? [this.translate.instant('filter.badges.all') as string] : badges;
  }

  private formatDateBadge(dateFrom: string, dateTo: string): string {
    const dateLabel = this.translate.instant('filter.badges.date') as string;
    const untilLabel = this.translate.instant('filter.badges.until') as string;
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
