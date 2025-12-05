import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

// Definition der verfügbaren DaisyUI Größen und Farben
export type InputSize = 'xs' | 'sm' | 'md' | 'lg';
export type InputColor = 'primary' | 'secondary' | 'accent' | 'info' | 'success' | 'warning' | 'error' | 'ghost' | 'bordered' | 'neutral';
export type InputShape = 'square' | 'circle';

@Component({
  selector: 'input-field',
  standalone: true,
  imports: [CommonModule, FormsModule], 
  templateUrl: './input-field.component.html',
  styleUrl: './input-field.component.css',
})
export class InputFieldComponent {
  @Input() label = ''; 
  @Input() placeholder = 'input';
  @Input() value = '';
  @Input() disabled = false;

  // Date input attributes
  @Input() min = '';
  @Input() max = ''; 
  
  // Default-Icon.
  @Input() showIcon = true; 
  @Input() icon = 'bi bi-search';
  
  // (text, password, date, email, etc.)
  @Input() type = 'text';
  @Input() shape: InputShape = 'square'; 

  // NEU: DaisyUI Size (Default 'md' entspricht ca. 3rem Höhe)
  @Input() size: InputSize = 'md';

  // NEU: DaisyUI Color Style (Default 'bordered')
  @Input() color: InputColor = 'bordered';

  onInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.value = target.value;
  }
}
