import { Component, input, forwardRef, ChangeDetectionStrategy, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, NG_VALUE_ACCESSOR, ControlValueAccessor } from '@angular/forms';

// Definition der verfügbaren DaisyUI Größen und Farben
export type InputSize = 'xs' | 'sm' | 'md' | 'lg';
export type InputColor =
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'info'
  | 'success'
  | 'warning'
  | 'error'
  | 'ghost'
  | 'bordered'
  | 'neutral';
export type InputShape = 'square' | 'circle';

@Component({
  selector: 'aql-input-field',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './input-field.component.html',
  styleUrl: './input-field.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => AqlInputFieldComponent),
      multi: true,
    },
  ],
})
export class AqlInputFieldComponent implements ControlValueAccessor {
  // Configuration inputs
  readonly label = input<string>('');
  readonly placeholder = input<string>('input');
  readonly min = input<string>('');
  readonly max = input<string>('');
  readonly showIcon = input<boolean>(true);
  readonly icon = input<string>('bi bi-search');
  readonly type = input<string>('text');
  readonly shape = input<InputShape>('square');
  readonly size = input<InputSize>('md');
  readonly color = input<InputColor>('bordered');
  private _value = '';

  @Input()
  set value(v: string) {
    this._value = v || '';
  }
  get value() {
    return this._value;
  }

  private _disabled = false;

  @Input()
  set disabled(v: boolean) {
    this._disabled = !!v;
  }
  get disabled() {
    return this._disabled;
  }
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  onChange: (value: string) => void = () => {};
  // eslint-disable-next-line @typescript-eslint/no-empty-function
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
