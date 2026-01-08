import {
  Component,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  OnInit,
  output,
  input,
  signal,
  computed,
  effect,
  inject,
} from '@angular/core';
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
import { FilterState, Provider } from '../../models/filter.model';
import { ProviderService, ProviderOption } from '../../services/provider.service';

@Component({
  selector: 'aql-filter-dropdown',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlInputFieldComponent,
    AqlRadioButtonComponent,
    AqlCheckboxComponent,
    AqlTooltipDirective,
  ],
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.css'],
})
export class FilterDropdownComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;

  private readonly providerService = inject(ProviderService);

  readonly filters = input<FilterState | null>(null);
  readonly filtersChanged = output<FilterState>();

  readonly dateFrom = signal<string>('');
  readonly dateTo = signal<string>('');
  readonly status = signal<string>('any');
  readonly isOpen = signal<boolean>(false);
  readonly providers = signal<Provider[]>([]);
  readonly providerSearch = signal<string>('');
  readonly isLoadingProviders = signal<boolean>(true);
  readonly providerLoadError = signal<boolean>(false);

  private previousOpenState = false;
  private checkInterval: number | null = null;
  private appliedClose = false;

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
    const today = new Date();
    return today.toISOString().split('T')[0];
  });

  readonly maxDateFrom = computed(() => {
    const dateTo = this.dateTo();
    if (dateTo) {
      const toDate = new Date(dateTo);
      toDate.setDate(toDate.getDate() - 1);
      return toDate.toISOString().split('T')[0];
    }
    return this.todayDate();
  });

  readonly minDateTo = computed(() => {
    const dateFrom = this.dateFrom();
    if (!dateFrom) return '';

    const fromDate = new Date(dateFrom);
    fromDate.setDate(fromDate.getDate() + 1);
    return fromDate.toISOString().split('T')[0];
  });

  readonly maxDateTo = computed(() => this.todayDate());

  constructor() {
    effect(() => {
      const filterValue = this.filters();
      if (filterValue) {
        this.dateFrom.set(filterValue.dateFrom || '');
        this.dateTo.set(filterValue.dateTo || '');
        this.status.set(filterValue.status || 'any');

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

  private loadProviders(): void {
    this.isLoadingProviders.set(true);
    this.providerLoadError.set(false);

    this.providerService.getProviders().subscribe({
      next: (providerOptions: ProviderOption[]) => {
        const providerList: Provider[] = [
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

  ngAfterViewInit(): void {
    this.checkInterval = window.setInterval(() => {
      if (this.dropdown) {
        const isOpen = this.dropdown.open;
        this.isOpen.set(isOpen);

        if (this.previousOpenState && !isOpen) {
          setTimeout(() => {
            if (!this.appliedClose) {
              this.reset();
            }
            this.appliedClose = false;
          }, 300);
        }

        this.previousOpenState = isOpen;
      }
    }, 50);
  }

  ngOnDestroy(): void {
    if (this.checkInterval !== null) {
      clearInterval(this.checkInterval);
    }
  }

  reset(): void {
    this.dateFrom.set('');
    this.dateTo.set('');
    this.status.set('any');
    this.providerSearch.set('');
    this.providers.update(providers => providers.map(p => ({ ...p, checked: p.label === 'All' })));

    this.emitCurrentState();
  }

  apply(event: MouseEvent): void {
    this.emitCurrentState();
    this.appliedClose = true;
    this.dropdown?.onContentClick(event);
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
    };

    this.filtersChanged.emit(currentState);
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
}
