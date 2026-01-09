import { Component, input, output, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

export type RadioSize = 'xs' | 'sm' | 'md' | 'lg';

@Component({
  selector: 'aql-radio-button',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './radio-button.component.html',
  styleUrl: './radio-button.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlRadioButtonComponent {
  readonly label = input<string>('');
  readonly name = input<string>('radio-group');
  readonly value = input<string | number>('');

  // Model Binding
  readonly checked = input<boolean>(false);
  readonly disabled = input<boolean>(false);

  // DaisyUI Größen
  readonly size = input<RadioSize>('md');

  readonly radioChange = output<string | number>();

  onChange() {
    if (this.disabled()) return;
    this.radioChange.emit(this.value());
  }
}
