import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type CheckboxSize = 'xs' | 'sm' | 'md' | 'lg';

@Component({
  selector: 'checkbox',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './checkbox.component.html',
  styleUrl: './checkbox.component.css',
})
export class CheckboxComponent {
  @Input() label = '';
  @Input() checked = false;
  @Input() disabled = false;
  
  // Neuer Input für den "Teilweise ausgewählt" Status
  @Input() indeterminate = false;

  // DaisyUI Size
  @Input() size: CheckboxSize = 'md';

  @Output() change = new EventEmitter<boolean>();
  @Output() indeterminateChange = new EventEmitter<boolean>();

  onChange(event: Event) {
    if (this.disabled) return;
    
    const target = event.target as HTMLInputElement;
    this.checked = target.checked;
    
    // Wenn man klickt, wird indeterminate in der Regel aufgehoben
    this.indeterminate = false;
    this.indeterminateChange.emit(this.indeterminate);
    
    this.change.emit(this.checked);
  }
}