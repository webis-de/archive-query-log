import { Component, input, output } from '@angular/core';
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
  // Modern Angular signals-based inputs/outputs
  readonly label = input<string>('');
  readonly checked = input<boolean>(false);
  readonly disabled = input<boolean>(false);
  readonly indeterminate = input<boolean>(false);
  readonly size = input<CheckboxSize>('md');

  readonly change = output<boolean>();
  readonly indeterminateChange = output<boolean>();

  onChange(checked: boolean): void {
    if (this.disabled()) return;

    this.change.emit(checked);

    if (this.indeterminate()) {
      this.indeterminateChange.emit(false);
    }
  }
}