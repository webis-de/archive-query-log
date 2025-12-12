import { Injectable } from '@angular/core';
import { FilterState } from '../models/filter.model';

@Injectable({
  providedIn: 'root',
})
export class FilterBadgeService {
  generateBadges(filters: FilterState): string[] {
    const badges: string[] = [];

    if (filters.dateFrom || filters.dateTo) {
      badges.push(this.formatDateBadge(filters.dateFrom, filters.dateTo));
    }

    if (filters.status && filters.status !== 'any') {
      badges.push(`Status: ${filters.status}`);
    }

    if (filters.providers && filters.providers.length > 0) {
      filters.providers.forEach(p => badges.push(`Provider: ${p}`));
    }

    return badges.length === 0 ? ['All'] : badges;
  }

  private formatDateBadge(dateFrom: string, dateTo: string): string {
    let dateStr = 'Date: ';

    if (dateFrom && dateTo) {
      dateStr += `${dateFrom} - ${dateTo}`;
    } else if (dateFrom) {
      dateStr += dateFrom;
    } else if (dateTo) {
      dateStr += `Until ${dateTo}`;
    }

    return dateStr;
  }
}
