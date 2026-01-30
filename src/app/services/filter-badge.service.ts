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

    if (filters.year) {
      const yearLabel = this.translate.instant('filter.badges.year') as string;
      badges.push(`${yearLabel}: ${filters.year}`);
    }

    if (filters.status && filters.status !== 'any') {
      const statusLabel = this.translate.instant('filter.badges.status') as string;
      const statusValue = this.translate.instant(`filter.${filters.status}`) as string;
      badges.push(`${statusLabel}: ${statusValue}`);
    }

    if (filters.provider) {
      const providerLabel = this.translate.instant('filter.badges.provider') as string;
      badges.push(`${providerLabel}: ${filters.provider}`);
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
}
