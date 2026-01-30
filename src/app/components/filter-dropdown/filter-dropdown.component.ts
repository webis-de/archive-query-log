import {
  Component,
  ViewChild,
  OnInit,
  output,
  input,
  inject,
  signal,
  computed,
  effect,
  ChangeDetectionStrategy,
} from '@angular/core';
import { ScrollingModule } from '@angular/cdk/scrolling';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlInputFieldComponent,
  AqlRadioButtonComponent,
  AqlCheckboxComponent,
  AqlTooltipDirective,
} from 'aql-stylings';

import { FilterState, FilterProvider } from '../../models/filter.model';
import { ProviderService, ProviderDetail } from '../../services/provider.service';
import { LanguageService } from '../../services/language.service';

@Component({
  selector: 'aql-filter-dropdown',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    ScrollingModule,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlInputFieldComponent,
    AqlRadioButtonComponent,
    AqlCheckboxComponent,
    AqlTooltipDirective,

  ],
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilterDropdownComponent implements OnInit {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;
  readonly filters = input<FilterState | null>(null);
  readonly filtersChanged = output<FilterState>();
  readonly dateFrom = signal<string>('');
  readonly dateTo = signal<string>('');
  readonly status = signal<string>('any');
  readonly advancedMode = signal<boolean>(false);
  readonly fuzzySearch = signal<boolean>(false);
  readonly placeholderToggle = signal<boolean>(false);
  readonly fuzziness = signal<'AUTO' | '0' | '1' | '2'>('AUTO');
  readonly expandSynonyms = signal<boolean>(false);
  readonly isOpen = signal<boolean>(false);
  readonly providers = signal<FilterProvider[]>([]);
  readonly providerSearch = signal<string>('');
  readonly isLoadingProviders = signal<boolean>(true);
  readonly providerLoadError = signal<boolean>(false);
  // Filtered providers based on search input
  readonly filteredProviders = computed(() => {
    const allProviders = this.providers();
    const searchTerm = this.providerSearch().toLowerCase().trim();

    if (!searchTerm) {
      return allProviders;
    }

    // Always keep "All" option visible, filter the rest
    return allProviders.filter(
      p => p.label === 'All' || p.label.toLowerCase().includes(searchTerm),
    );
  });
  // Count of selected providers (excluding "All")
  readonly selectedProviderCount = computed(() => {
    return this.providers().filter(p => p.checked && p.label !== 'All').length;
  });
  readonly todayDate = computed(() => {
    return this.languageService.formatDateForInput(new Date());
  });
  readonly maxDateFrom = computed(() => {
    const dateTo = this.dateTo();
    if (dateTo) {
      const toDate = new Date(dateTo);
      toDate.setDate(toDate.getDate() - 1);
      return this.languageService.formatDateForInput(toDate);
    }
    return this.todayDate();
  });
  readonly minDateTo = computed(() => {
    const dateFrom = this.dateFrom();
    if (!dateFrom) return '';

    const fromDate = new Date(dateFrom);
    fromDate.setDate(fromDate.getDate() + 1);
    return this.languageService.formatDateForInput(fromDate);
  });
  readonly maxDateTo = computed(() => this.todayDate());

  private readonly providerService = inject(ProviderService);
  private readonly languageService = inject(LanguageService);
  private previousOpenState = false;
  private appliedClose = false;

  constructor() {
    effect(() => {
      const filterValue = this.filters();
      if (filterValue) {
        this.dateFrom.set(filterValue.dateFrom || '');
        this.dateTo.set(filterValue.dateTo || '');
        this.status.set(filterValue.status || 'any');
        this.advancedMode.set(filterValue.advancedMode || false);
        this.fuzzySearch.set(filterValue.fuzzy ?? false);
        this.fuzziness.set(filterValue.fuzziness ?? 'AUTO');
        this.expandSynonyms.set(filterValue.expandSynonyms ?? false);

        if (filterValue.providers && filterValue.providers.length > 0) {
          this.providers.update(providers =>
            providers.map(p => ({
              ...p,
              checked: p.label === 'All' ? false : filterValue.providers.includes(p.label),
            })),
          );
        }
      }
    });
  }



  ngOnInit(): void {
    this.loadProviders();
  }

  onDropdownOpenChange(isOpen: boolean): void {
    const wasOpen = this.previousOpenState;
    this.previousOpenState = isOpen;
    this.isOpen.set(isOpen);

    // Reset filters when dropdown closes without applying
    if (wasOpen && !isOpen) {
      setTimeout(() => {
        if (!this.appliedClose) {
          this.reset();
        }
        this.appliedClose = false;
      }, 300);
    }
  }

  reset(): void {
    this.dateFrom.set('');
    this.dateTo.set('');
    this.status.set('any');
    this.advancedMode.set(false);
    this.fuzzySearch.set(false);
    this.fuzziness.set('AUTO');
    this.expandSynonyms.set(false);
    this.providerSearch.set('');
    this.providers.update(providers => providers.map(p => ({ ...p, checked: p.label === 'All' })));

    this.emitCurrentState();
  }

  apply(event: MouseEvent): void {
    this.emitCurrentState();
    this.appliedClose = true;
    this.dropdown?.onContentClick(event);
  }

  updateDateFrom(value: string): void {
    this.dateFrom.set(value);
  }

  updateDateTo(value: string): void {
    this.dateTo.set(value);
  }

  updateStatus(value: string): void {
    this.status.set(value);
  }

  updateAdvancedMode(value: boolean): void {
    this.advancedMode.set(value);
  }

  updateFuzzySearch(value: boolean): void {
    this.fuzzySearch.set(value);
    this.emitCurrentState();
  }

  updatePlaceholderToggle(value: boolean): void {
    this.placeholderToggle.set(value);
    this.emitCurrentState();
  }

  updateFuzziness(value: 'AUTO' | '0' | '1' | '2'): void {
    this.fuzziness.set(value);
  }

  updateExpandSynonyms(value: boolean): void {
    this.expandSynonyms.set(value);
  }

  updateProviderSearch(value: string): void {
    this.providerSearch.set(value);
  }

  updateProviderCheckedByLabel(label: string, checked: boolean): void {
    this.providers.update(providers => {
      if (label === 'All' && checked) {
        return providers.map(p => ({ ...p, checked: p.label === 'All' }));
      } else if (label === 'All' && !checked) {
        const hasOtherSelected = providers.some(p => p.label !== 'All' && p.checked);
        if (!hasOtherSelected) {
          return providers;
        }
        return providers.map(p => (p.label === label ? { ...p, checked } : p));
      } else if (label !== 'All' && checked) {
        return providers.map(p => {
          if (p.label === 'All') return { ...p, checked: false };
          if (p.label === label) return { ...p, checked };
          return p;
        });
      } else {
        const updatedProviders = providers.map(p => (p.label === label ? { ...p, checked } : p));
        const hasAnySelected = updatedProviders.some(p => p.label !== 'All' && p.checked);
        if (!hasAnySelected) {
          return updatedProviders.map(p => (p.label === 'All' ? { ...p, checked: true } : p));
        }
        return updatedProviders;
      }
    });
  }

  trackByProviderId(index: number, item: FilterProvider): string {
    return item.id;
  }

  private loadProviders(): void {
    this.isLoadingProviders.set(true);
    this.providerLoadError.set(false);

    this.providerService.getProviders().subscribe({
      next: (providerOptions: ProviderDetail[]) => {
        const providerList: FilterProvider[] = [
          { id: 'all', label: 'All', checked: true },
          ...providerOptions.map(p => ({
            id: p.id,
            label: p.name,
            checked: false,
          })),
        ];
        this.providers.set(providerList);
        this.isLoadingProviders.set(false);

        // Re-apply filter state if it was set before providers loaded
        const filterValue = this.filters();
        if (filterValue?.providers && filterValue.providers.length > 0) {
          this.providers.update(providers =>
            providers.map(p => ({
              ...p,
              checked: p.label === 'All' ? false : filterValue.providers.includes(p.label),
            })),
          );
        }
      },
      error: () => {
        this.isLoadingProviders.set(false);
        this.providerLoadError.set(true);
        // Set fallback with only "All" option
        this.providers.set([{ id: 'all', label: 'All', checked: true }]);
      },
    });
  }

  private emitCurrentState(): void {
    const selectedProviders = this.providers()
      .filter(p => p.checked && p.label !== 'All')
      .map(p => p.label);

    const currentState: FilterState = {
      dateFrom: this.dateFrom(),
      dateTo: this.dateTo(),
      status: this.status(),
      providers: selectedProviders,
      advancedMode: this.advancedMode(),
      fuzzy: this.fuzzySearch(),
      fuzziness: this.fuzziness(),
      expandSynonyms: this.expandSynonyms(),
    };

    this.filtersChanged.emit(currentState);
  }
}
