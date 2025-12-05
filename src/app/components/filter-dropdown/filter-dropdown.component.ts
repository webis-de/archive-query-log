// filter-dropdown.component.ts
import { Component, ViewChild, AfterViewInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  AqlDropdownComponent,
  AqlButtonComponent,
  InputFieldComponent,
  RadioButtonComponent,
  CheckboxComponent,
} from 'aql-stylings';

@Component({
  selector: 'aql-filter-dropdown',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    AqlDropdownComponent,
    AqlButtonComponent,
    InputFieldComponent,
    RadioButtonComponent,
    CheckboxComponent,
  ],
  templateUrl: './filter-dropdown.component.html',
  styleUrls: ['./filter-dropdown.component.css'],
})
export class FilterDropdownComponent implements AfterViewInit, OnDestroy {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;

  dateFrom = '';
  dateTo = '';
  status = 'any';
  private previousOpenState = false;
  private checkInterval: number | null = null;

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

        // Detect transition from open to closed
        if (this.previousOpenState && !isOpen) {
          setTimeout(() => {
            this.reset();
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
    console.log('Filters applied:', {
      from: this.dateFrom,
      to: this.dateTo,
      status: this.status,
      providers: this.providers.filter(p => p.checked).map(p => p.label),
    });

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
