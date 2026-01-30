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
  AqlTooltipDirective,
} from 'aql-stylings';

import { FilterState, FilterProvider } from '../../models/filter.model';
import { ProviderService, ProviderDetail } from '../../services/provider.service';

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
  readonly selectedYear = signal<number | undefined>(undefined);
  readonly status = signal<string>('any');
  readonly advancedMode = signal<boolean>(false);
  readonly fuzzySearch = signal<boolean>(false);
  readonly fuzziness = signal<'AUTO' | '0' | '1' | '2'>('AUTO');
  readonly expandSynonyms = signal<boolean>(false);
  readonly isOpen = signal<boolean>(false);
  readonly providers = signal<FilterProvider[]>([]);
  readonly selectedProvider = signal<string | undefined>(undefined); // Store provider ID
  readonly providerSearch = signal<string>('');
  readonly isLoadingProviders = signal<boolean>(true);
  readonly providerLoadError = signal<boolean>(false);

  // Available years for the dropdown (current year down to a reasonable past year)
  readonly availableYears = computed(() => {
    const currentYear = new Date().getFullYear();
    const years: number[] = [];
    for (let year = currentYear; year >= 2000; year--) {
      years.push(year);
    }
    return years;
  });

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

  // Check if a specific provider is selected (not "All")
  readonly hasProviderSelected = computed(() => {
    return this.selectedProvider() !== undefined;
  });

  private readonly providerService = inject(ProviderService);
  private previousOpenState = false;

  // Store the last applied filter state to restore when closing without apply
  private lastAppliedState: FilterState = {
    year: undefined,
    status: 'any',
    provider: undefined,
    advancedMode: false,
    fuzzy: false,
    fuzziness: 'AUTO',
    expandSynonyms: false,
  };

  constructor() {
    effect(() => {
      const filterValue = this.filters();
      if (filterValue) {
        this.selectedYear.set(filterValue.year);
        this.status.set(filterValue.status || 'any');
        this.advancedMode.set(filterValue.advancedMode || false);
        this.fuzzySearch.set(filterValue.fuzzy ?? false);
        this.fuzziness.set(filterValue.fuzziness ?? 'AUTO');
        this.expandSynonyms.set(filterValue.expandSynonyms ?? false);
        this.selectedProvider.set(filterValue.provider);
        // Update the last applied state when filters are set externally
        this.lastAppliedState = { ...filterValue };
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

    // When dropdown closes without applying, restore to last applied state
    if (wasOpen && !isOpen) {
      setTimeout(() => {
        this.restoreLastAppliedState();
      }, 300);
    }
  }

  /**
   * Restores the UI to the last applied filter state.
   * Called when dropdown closes without clicking Apply.
   */
  private restoreLastAppliedState(): void {
    this.selectedYear.set(this.lastAppliedState.year);
    this.status.set(this.lastAppliedState.status || 'any');
    this.advancedMode.set(this.lastAppliedState.advancedMode || false);
    this.fuzzySearch.set(this.lastAppliedState.fuzzy ?? false);
    this.fuzziness.set(this.lastAppliedState.fuzziness ?? 'AUTO');
    this.expandSynonyms.set(this.lastAppliedState.expandSynonyms ?? false);
    this.selectedProvider.set(this.lastAppliedState.provider);
    this.providerSearch.set('');
  }

  reset(): void {
    this.selectedYear.set(undefined);
    this.status.set('any');
    this.advancedMode.set(false);
    this.fuzzySearch.set(false);
    this.fuzziness.set('AUTO');
    this.expandSynonyms.set(false);
    this.providerSearch.set('');
    this.selectedProvider.set(undefined);

    // Update the last applied state and emit
    this.lastAppliedState = {
      year: undefined,
      status: 'any',
      provider: undefined,
      advancedMode: false,
      fuzzy: false,
      fuzziness: 'AUTO',
      expandSynonyms: false,
    };
    this.emitCurrentState();
  }

  apply(event: MouseEvent): void {
    // Save the current state as the last applied state
    this.lastAppliedState = {
      year: this.selectedYear(),
      status: this.status(),
      provider: this.selectedProvider(),
      advancedMode: this.advancedMode(),
      fuzzy: this.fuzzySearch(),
      fuzziness: this.fuzziness(),
      expandSynonyms: this.expandSynonyms(),
    };
    this.emitCurrentState();
    this.dropdown?.onContentClick(event);
  }

  updateYear(value: string): void {
    if (value === '' || value === 'any') {
      this.selectedYear.set(undefined);
    } else {
      this.selectedYear.set(parseInt(value, 10));
    }
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

  updateFuzziness(value: 'AUTO' | '0' | '1' | '2'): void {
    this.fuzziness.set(value);
  }

  updateExpandSynonyms(value: boolean): void {
    this.expandSynonyms.set(value);
  }

  updateProviderSearch(value: string): void {
    this.providerSearch.set(value);
  }

  // Single provider selection - radio button behavior
  selectProvider(providerId: string | undefined): void {
    this.selectedProvider.set(providerId);
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
          { id: 'all', label: 'All', checked: false },
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
        if (filterValue?.provider) {
          this.selectedProvider.set(filterValue.provider);
        }
      },
      error: () => {
        this.isLoadingProviders.set(false);
        this.providerLoadError.set(true);
        // Set fallback with only "All" option
        this.providers.set([{ id: 'all', label: 'All', checked: false }]);
      },
    });
  }

  private emitCurrentState(): void {
    const currentState: FilterState = {
      year: this.selectedYear(),
      status: this.status(),
      provider: this.selectedProvider(), // undefined means "All" (no filter)
      advancedMode: this.advancedMode(),
      fuzzy: this.fuzzySearch(),
      fuzziness: this.fuzziness(),
      expandSynonyms: this.expandSynonyms(),
    };

    this.filtersChanged.emit(currentState);
  }
}
