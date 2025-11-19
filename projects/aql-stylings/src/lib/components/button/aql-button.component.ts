import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

export type ButtonType = 'default' | 'primary' | 'secondary' | 'accent' | 'ghost' | 'link';

// daisyUI utility classes (only for 1:1 ratio buttons)
export type IconStyle = 'default' | 'square' | 'circle';

// custom utility classes (for border-radius variants)
export type BtnStyle = 'default' | 'rounded' | 'full';

@Component({
  selector: 'aql-button',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-button.component.html',
  styleUrl: './aql-button.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlButtonComponent {
  @Input() btnType: ButtonType = 'default';
  @Input() iconStyle?: IconStyle;
  @Input() btnStyle: BtnStyle = 'default';
  @Input() disabled = false;
  @Input() iconBefore?: string;
  @Input() iconAfter?: string;
  @Input() fullWidth = false;
  @Input() outline = false;
  @Input() soft = false;
  @Input() flatten = false;
  @Input() isLoading = false;
  @Input() size: 'xs' | 'sm' | 'md' | 'lg' = 'md';

  @Output() buttonClick = new EventEmitter<MouseEvent>();

  get buttonClasses(): string {
    const classes: string[] = ['btn'];

    if (this.soft) {
      classes.push('btn-soft');
    }

    if (this.outline) {
      classes.push('btn-outline');
    }

    if (this.flatten) {
      classes.push('btn-flatten');
    }

    if (this.btnType !== 'default') {
      classes.push(`btn-${this.btnType}`);
    }

    if (this.iconStyle === 'square') {
      classes.push('btn-square');
    } else if (this.iconStyle === 'circle') {
      classes.push('btn-circle');
    }

    if (this.btnStyle === 'rounded') {
      classes.push('btn-rounded');
    } else if (this.btnStyle === 'full') {
      classes.push('btn-full');
    }

    if (this.size !== 'md') {
      classes.push(`btn-${this.size}`);
    }
    if (this.fullWidth) {
      classes.push('btn-block');
    }

    return classes.join(' ');
  }

  onClick(event: MouseEvent): void {
    if (!this.disabled) {
      this.buttonClick.emit(event);
    }
  }
}
