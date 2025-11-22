import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

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
  
  // Default-Icon.
  @Input() showIcon = true; 
  
  // (text, password, date, email, etc.)
  @Input() type = 'text';

  @Input() shape: InputShape = 'square'; 

  onInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.value = target.value;
  }
}
