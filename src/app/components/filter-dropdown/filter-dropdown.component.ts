// filter-dropdown.component.ts
import { Component, ViewChild, AfterViewInit, OnDestroy, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AqlDropdownComponent,
  AqlButtonComponent,
  AqlInputFieldComponent,
  RadioButtonComponent,
  CheckboxComponent,
} from 'aql-stylings';

export interface FilterState {
  dateFrom: string;
  dateTo: string;
  status: string;
  providers: string[];
}

@Component({
  selector: 'aql-filter-dropdown',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlInputFieldComponent,
    RadioButtonComponent,
    CheckboxComponent,
  ],
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.css'],
})
export class FilterDropdownComponent implements AfterViewInit, OnDestroy {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;

  @Output() filtersChanged = new EventEmitter<FilterState>();

  dateFrom = '';
  dateTo = '';
  status = 'any';
  isOpen = false; // Track dropdown open state for icon change
  private previousOpenState = false;
  private checkInterval: number | null = null;
  private appliedClose = false; // Track if close was triggered by Apply button

  providers = [
    { label: 'Google', checked: false },
    { label: 'Bing', checked: false },
    { label: 'DuckDuckGo', checked: false },
    { label: 'Yahoo', checked: false },
  ];

  ngAfterViewInit(): void {
    // Monitor the dropdown's open state
    this.checkInterval = window.setInterval(() => {
      if (this.dropdown) {
        const isOpen = this.dropdown.open;

        // Update the public isOpen property for the template
        this.isOpen = isOpen;

        // Detect transition from open to closed
        if (this.previousOpenState && !isOpen) {
          setTimeout(() => {
            // Only reset if the close was NOT triggered by Apply button
            if (!this.appliedClose) {
              this.reset();
            }
            this.appliedClose = false; // Reset the flag for next time
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

  reset() {
    this.dateFrom = '';
    this.dateTo = '';
    this.status = 'any';
    // Re-create array objects to force re-render of list items, ensuring checkboxes reset visually
    this.providers = this.providers.map(p => ({ ...p, checked: false }));
  }

  apply(event: MouseEvent) {
    const currentState: FilterState = {
      dateFrom: this.dateFrom,
      dateTo: this.dateTo,
      status: this.status,
      providers: this.providers.filter(p => p.checked).map(p => p.label),
    };

    console.log('Filters applied:', currentState);
    this.filtersChanged.emit(currentState);

    // Mark that this close was triggered by Apply (so we don't reset)
    this.appliedClose = true;

    // Dropdown gezielt schließen, über die interne Click-Logik
    this.dropdown?.onContentClick(event);
  }

  /**
   * Get today's date in YYYY-MM-DD format to prevent future dates
   */
  getTodayDate(): string {
    const today = new Date();
    return today.toISOString().split('T')[0];
  }

  /**
   * Get the maximum date for the "From" field
   * - If "To" date is set, max is one day before "To"
   * - Otherwise, max is today
   */
  getMaxDateFrom(): string {
    if (this.dateTo) {
      const toDate = new Date(this.dateTo);
      toDate.setDate(toDate.getDate() - 1);
      return toDate.toISOString().split('T')[0];
    }
    return this.getTodayDate();
  }

  /**
   * Get the minimum date for the "To" field (must be after "From" date)
   */
  getMinDateTo(): string {
    if (!this.dateFrom) return '';

    const fromDate = new Date(this.dateFrom);
    fromDate.setDate(fromDate.getDate() + 1);

    return fromDate.toISOString().split('T')[0];
  }

  /**
   * Get the maximum date for the "To" field (today)
   */
  getMaxDateTo(): string {
    return this.getTodayDate();
  }
}
