import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

export type ButtonType = 'default' | 'primary' | 'secondary' | 'accent' | 'ghost' | 'link' | 'icon';

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
  @Input() align: 'start' | 'center' | 'end' = 'center';

  @Output() buttonClick = new EventEmitter<MouseEvent>();

  get buttonClasses(): string {
    if (this.btnType === 'icon') {
      return this.getIconButtonClasses();
    }

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

    if (this.align === 'start') {
      classes.push('justify-start');
    } else if (this.align === 'end') {
      classes.push('justify-end');
    }

    return classes.join(' ');
  }

  private getIconButtonClasses(): string {
    const classes: string[] = [
      'inline-flex',
      'items-center',
      'justify-center',
      'gap-2',
      'rounded-md',
      'bg-transparent',
      'text-base-content/60',
      'transition-colors',
      'cursor-pointer',
      'hover:text-base-content',
      'focus-visible:text-base-content',
      'focus-visible:outline-none',
      'focus-visible:ring',
      'focus-visible:ring-primary/30',
      'disabled:text-base-content/40',
      'disabled:cursor-not-allowed',
    ];

    if (this.size === 'xs') {
      classes.push('text-xs', 'p-1.5');
    } else if (this.size === 'sm') {
      classes.push('text-sm', 'p-1.5');
    } else if (this.size === 'lg') {
      classes.push('text-lg', 'p-2.5');
    }

    if (this.iconStyle === 'square') {
      classes.push('aspect-square', 'w-10', 'h-10');
    } else if (this.iconStyle === 'circle') {
      classes.push('aspect-square', 'w-10', 'h-10', 'rounded-full');
    }

    return classes.join(' ');
  }

  onClick(event: MouseEvent): void {
    if (!this.disabled) {
      this.buttonClick.emit(event);
    }
  }
}
