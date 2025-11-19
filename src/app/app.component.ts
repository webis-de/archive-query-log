import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AqlButtonComponent, AqlDropdownComponent } from 'aql-stylings';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AqlButtonComponent, AqlDropdownComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css',
})
export class AppComponent {
  title = 'aql-frontend';
}
