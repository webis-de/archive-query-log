import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InputFieldComponent, AqlButtonComponent } from 'aql-stylings';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [CommonModule, InputFieldComponent, AqlButtonComponent],
  templateUrl: './landing.component.html',
  styleUrl: './landing.component.css',
})
export class LandingComponent {}
