// filter-dropdown.component.ts
import { Component, ViewChild } from '@angular/core';
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
export class FilterDropdownComponent {
  @ViewChild(AqlDropdownComponent)
  dropdown?: AqlDropdownComponent;

  dateFrom = '';
  dateTo = '';
  status = 'any';

  providers = [
    { label: 'Google', checked: false },
    { label: 'Bing', checked: false },
    { label: 'DuckDuckGo', checked: false },
    { label: 'Yahoo', checked: false },
  ];

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
}
