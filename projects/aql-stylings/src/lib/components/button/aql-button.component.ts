import { ChangeDetectionStrategy, Component, input, output, computed } from '@angular/core';
import { CommonModule } from '@angular/common';

export type ButtonType =
  | 'default'
  | 'primary'
  | 'secondary'
  | 'accent'
  | 'ghost'
  | 'link'
  | 'icon'
  | 'error';

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
  readonly btnType = input<ButtonType>('default');
  readonly iconStyle = input<IconStyle | undefined>(undefined);
  readonly btnStyle = input<BtnStyle>('default');
  readonly disabled = input<boolean>(false);
  readonly iconBefore = input<string | undefined>(undefined);
  readonly iconAfter = input<string | undefined>(undefined);
  readonly fullWidth = input<boolean>(false);
  readonly outline = input<boolean>(false);
  readonly soft = input<boolean>(false);
  readonly flatten = input<boolean>(false);
  readonly isLoading = input<boolean>(false);
  readonly size = input<'xs' | 'sm' | 'md' | 'lg'>('md');
  readonly align = input<'start' | 'center' | 'end'>('center');

  readonly buttonClick = output<MouseEvent>();

  readonly iconClasses = computed<string>(() => {
    if (this.btnType() !== 'icon') return '';

    const classes: string[] = [];

    const size = this.size();
    if (size === 'xs') {
      classes.push('text-sm');
    } else if (size === 'sm') {
      classes.push('text-lg');
    } else if (size === 'md') {
      classes.push('text-xl');
    } else if (size === 'lg') {
      classes.push('text-2xl');
    }

    return classes.join(' ');
  });

  readonly buttonClasses = computed<string>(() => {
    if (this.btnType() === 'icon') {
      return this.getIconButtonClasses();
    }

    const classes: string[] = ['btn'];

    if (this.soft()) {
      classes.push('btn-soft');
    }

    if (this.outline()) {
      classes.push('btn-outline');
    }

    if (this.flatten()) {
      classes.push('btn-flatten');
    }

    const btnType = this.btnType();
    if (btnType !== 'default') {
      classes.push(`btn-${btnType}`);
    }

    const iconStyle = this.iconStyle();
    if (iconStyle === 'square') {
      classes.push('btn-square');
    } else if (iconStyle === 'circle') {
      classes.push('btn-circle');
    }

    const btnStyle = this.btnStyle();
    if (btnStyle === 'rounded') {
      classes.push('btn-rounded');
    } else if (btnStyle === 'full') {
      classes.push('btn-full');
    }

    const size = this.size();
    if (size !== 'md') {
      classes.push(`btn-${size}`);
    }
    if (this.fullWidth()) {
      classes.push('btn-block');
    }

    const align = this.align();
    if (align === 'start') {
      classes.push('justify-start');
    } else if (align === 'end') {
      classes.push('justify-end');
    }

    return classes.join(' ');
  });

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
      'p-0',
    ];

    const size = this.size();
    if (size === 'xs') {
      classes.push('text-xs', 'w-4', 'h-4');
    } else if (size === 'sm') {
      classes.push('text-sm', 'w-5', 'h-5');
    } else if (size === 'md') {
      classes.push('text-base', 'w-6', 'h-6');
    } else if (size === 'lg') {
      classes.push('text-lg', 'w-8', 'h-8');
    }

    const iconStyle = this.iconStyle();
    if (iconStyle === 'square') {
      classes.push('aspect-square');
    } else if (iconStyle === 'circle') {
      classes.push('aspect-square', 'rounded-full');
    }

    return classes.join(' ');
  }

  onClick(event: MouseEvent): void {
    if (!this.disabled()) {
      this.buttonClick.emit(event);
    }
  }
}
