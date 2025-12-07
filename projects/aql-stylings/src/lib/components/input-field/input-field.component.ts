import { Component, Input, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NG_VALUE_ACCESSOR, ControlValueAccessor } from '@angular/forms';

// Definition der verfügbaren DaisyUI Größen und Farben
export type InputSize = 'xs' | 'sm' | 'md' | 'lg';
export type InputColor = 'primary' | 'secondary' | 'accent' | 'info' | 'success' | 'warning' | 'error' | 'ghost' | 'bordered' | 'neutral';
export type InputShape = 'square' | 'circle';

@Component({
  selector: 'aql-input-field',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './input-field.component.html',
  styleUrl: './input-field.component.css',
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => AqlInputFieldComponent),
      multi: true
    }
  ]
})
export class AqlInputFieldComponent implements ControlValueAccessor {
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

  value = '';

  onChange: (value: string) => void = () => {};
  onTouched: () => void = () => {};

  writeValue(value: string): void {
    this.value = value || '';
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }

  onInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.value = target.value;
    this.onChange(this.value);
    this.onTouched();
  }
}
