import {
  Component,
  viewChild,
  output,
  input,
  inject,
  signal,
  computed,
  effect,
  ChangeDetectionStrategy,
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
import { FilterState, FilterProvider } from '../../models/filter.model';
import { LanguageService } from '../../services/language.service';

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
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class FilterDropdownComponent {
  readonly dropdown = viewChild<AqlDropdownComponent>(AqlDropdownComponent);
  readonly filters = input<FilterState | null>(null);
  readonly filtersChanged = output<FilterState>();
  readonly dateFrom = signal<string>('');
  readonly dateTo = signal<string>('');
  readonly status = signal<string>('any');
  readonly isOpen = signal<boolean>(false);
  readonly providers = signal<FilterProvider[]>([
    { id: 'all', label: 'All', checked: true },
    { id: 'google', label: 'Google', checked: false },
    { id: 'bing', label: 'Bing', checked: false },
    { id: 'duckduckgo', label: 'DuckDuckGo', checked: false },
    { id: 'yahoo', label: 'Yahoo', checked: false },
  ]);
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

  private readonly languageService = inject(LanguageService);
  private appliedClose = false;

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

  onDropdownOpenChange(isOpen: boolean): void {
    const wasOpen = this.isOpen();
    this.isOpen.set(isOpen);

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
    this.providers.update(providers => providers.map(p => ({ ...p, checked: p.label === 'All' })));

    this.emitCurrentState();
  }

  apply(event: MouseEvent): void {
    this.emitCurrentState();
    this.appliedClose = true;
    this.dropdown()?.onContentClick(event);
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
}
