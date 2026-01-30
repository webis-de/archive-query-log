import { DestroyRef } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TranslateService } from '@ngx-translate/core';
import { FilterBadgeService } from '../services/filter-badge.service';
import { FilterState } from '../models/filter.model';

interface FilterBadgeControllerOptions {
  filterBadgeService: FilterBadgeService;
  translate: TranslateService;
  destroyRef: DestroyRef;
  getFilters: () => FilterState | null;
  setFilters: (filters: FilterState) => void;
  setBadges: (badges: string[]) => void;
}

export const createFilterBadgeController = (options: FilterBadgeControllerOptions) => {
  const { filterBadgeService, translate, destroyRef, getFilters, setFilters, setBadges } = options;
  const emptyFilters: FilterState = {
    status: 'any',
  };

  const refreshBadges = (): void => {
    const filters = getFilters();
    setBadges(filterBadgeService.generateBadges(filters ?? emptyFilters));
  };

  const onFiltersChanged = (filters: FilterState): void => {
    setFilters(filters);
    setBadges(filterBadgeService.generateBadges(filters));
  };

  translate.onLangChange.pipe(takeUntilDestroyed(destroyRef)).subscribe(() => {
    refreshBadges();
  });

  return {
    onFiltersChanged,
    refreshBadges,
  };
};
