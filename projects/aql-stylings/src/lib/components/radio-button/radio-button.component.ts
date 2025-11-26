import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type RadioSize = 'xs' | 'sm' | 'md' | 'lg';

@Component({
  selector: 'radio-button',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './radio-button.component.html',
  styleUrl: './radio-button.component.css',
})
export class RadioButtonComponent {
  @Input() label = '';
  @Input() name = 'radio-group';
  @Input() value: any;
  
  // Model Binding
  @Input() checked = false;
  @Input() disabled = false;

  // DaisyUI Größen
  @Input() size: RadioSize = 'md';

  @Output() change = new EventEmitter<any>();

  onChange() {
    if (this.disabled) return;
    this.checked = true;
    this.change.emit(this.value);
  }
}