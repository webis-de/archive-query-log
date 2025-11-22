import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AqlButtonComponent } from '../button/aql-button.component';

@Component({
  selector: 'input-field',
  standalone: true,
  imports: [CommonModule, FormsModule, AqlButtonComponent],
  templateUrl: './input-field.component.html',
  styleUrl: './input-field.component.css',
})
export class InputFieldComponent {
  @Input() label = ''; 
  @Input() placeholder = 'input';
  @Input() value = '';
  
 
  @Input() disabled = false; 


  @Input() showIcon = true;
  @Input() showButton = true;
  

  @Input() buttonText = 'Search';

  onInput(event: Event) {
    const target = event.target as HTMLInputElement;
    this.value = target.value;
  }
  

}