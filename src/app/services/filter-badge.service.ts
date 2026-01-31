import { Injectable, inject, signal } from '@angular/core';
import { TranslateService } from '@ngx-translate/core';
import { FilterState } from '../models/filter.model';
import { ProviderService, ProviderDetail } from './provider.service';

@Injectable({
  providedIn: 'root',
})
export class FilterBadgeService {
  private readonly translate = inject(TranslateService);
  private readonly providerService = inject(ProviderService);
  private providerMap = signal<Map<string, string>>(new Map());

  constructor() {
    // Load providers to build the ID -> name mapping
    this.providerService.getProviders().subscribe((providers: ProviderDetail[]) => {
      const map = new Map<string, string>();
      providers.forEach(p => map.set(p.id, p.name));
      this.providerMap.set(map);
    });
  }

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
      // Look up provider name from map, fall back to ID if not found
      const providerName = this.providerMap().get(filters.provider) || filters.provider;
      badges.push(`${providerLabel}: ${providerName}`);
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
