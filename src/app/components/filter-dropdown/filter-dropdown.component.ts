import {
  Component,
  ViewChild,
  AfterViewInit,
  OnDestroy,
  output,
  input,
  signal,
  computed,
  effect,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlInputFieldComponent,
  AqlRadioButtonComponent,
  AqlCheckboxComponent,
} from 'aql-stylings';
import { FilterState, Provider } from '../../models/filter.model';

@Component({
  selector: 'aql-filter-dropdown',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlInputFieldComponent,
    AqlRadioButtonComponent,
    AqlCheckboxComponent,
  ],
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.css'],
})
export class FilterDropdownComponent implements AfterViewInit, OnDestroy {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;

  readonly filters = input<FilterState | null>(null);
  readonly filtersChanged = output<FilterState>();

  readonly dateFrom = signal<string>('');
  readonly dateTo = signal<string>('');
  readonly status = signal<string>('any');
  readonly isOpen = signal<boolean>(false);
  readonly providers = signal<Provider[]>([
    { id: 'all', label: 'All', checked: true },
    { id: 'google', label: 'Google', checked: false },
    { id: 'bing', label: 'Bing', checked: false },
    { id: 'duckduckgo', label: 'DuckDuckGo', checked: false },
    { id: 'yahoo', label: 'Yahoo', checked: false },
  ]);

  private previousOpenState = false;
  private checkInterval: number | null = null;
  private appliedClose = false;

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

        if (filterValue.providers) {
          this.providers.update(providers =>
            providers.map(p => ({
              ...p,
              checked: filterValue.providers.includes(p.label),
            })),
          );
        }
      }
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
