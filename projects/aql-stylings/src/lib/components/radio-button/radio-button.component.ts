import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type RadioSize = 'xs' | 'sm' | 'md' | 'lg';

@Component({
  selector: 'aql-radio-button',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './radio-button.component.html',
  styleUrl: './radio-button.component.css',
})
export class AqlRadioButtonComponent {
  @Input() label = '';
  @Input() name = 'radio-group';
  @Input() value: string | number = '';

  // Model Binding
  @Input() checked = false;
  @Input() disabled = false;

  // DaisyUI Größen
  @Input() size: RadioSize = 'md';

  @Output() radioChange = new EventEmitter<string | number>();

  onChange() {
    if (this.disabled) return;
    this.checked = true;
    this.radioChange.emit(this.value);
  }
}
