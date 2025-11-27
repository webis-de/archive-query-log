import { Component } from '@angular/core';
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
}
