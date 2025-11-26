import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import {
  AqlButtonComponent,
  AqlDropdownComponent,
  AqlGroupItemComponent,
  AqlMenuItemComponent,
  CheckboxComponent,
  RadioButtonComponent,
} from 'aql-stylings';
import { AppSidebarComponent } from './components/sidebar/app-sidebar.component';
import { MOCK_USER_DATA } from './mock-data';
import { InputFieldComponent } from 'projects/aql-stylings/src/public-api';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    AppSidebarComponent,
    AqlMenuItemComponent,
    AqlDropdownComponent,
    AqlButtonComponent,
    AqlGroupItemComponent,
    InputFieldComponent,
    RadioButtonComponent,
    CheckboxComponent,
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  title = 'aql-frontend';
  userData = MOCK_USER_DATA;
}
