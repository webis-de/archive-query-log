import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostBinding,
  HostListener,
  Input,
  booleanAttribute,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';

type DropdownPositionSegment = 'bottom' | 'top' | 'left' | 'right' | 'start' | 'end';
export type DropdownPosition =
  | DropdownPositionSegment
  | `${DropdownPositionSegment}-${DropdownPositionSegment}`
  | `${DropdownPositionSegment} ${DropdownPositionSegment}`;

@Component({
  selector: 'aql-dropdown',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-dropdown.component.html',
  styleUrl: './aql-dropdown.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlDropdownComponent {
  private readonly elementRef = inject(ElementRef<HTMLElement>);

  readonly matchTriggerWidth = input(false, { transform: booleanAttribute });
  readonly contentWidth = input<string | null>('14rem');
  readonly position = input<DropdownPosition | undefined>('bottom');

  private readonly openState = signal(false);

  private readonly positionSegments = computed<ReadonlySet<DropdownPositionSegment>>(() => {
    const rawPosition = this.position() ?? 'bottom';
    const segments = rawPosition
      .split(/[\s-]+/)
      .map(segment => segment.trim())
      .filter(
        (segment): segment is DropdownPositionSegment =>
          segment.length > 0 && this.isValidPositionSegment(segment),
      );

    return new Set<DropdownPositionSegment>(segments.length ? segments : ['bottom']);
  });

  @Input()
  set open(value: boolean | string | null | undefined) {
    this.openState.set(this.coerceBoolean(value));
  }

  get open(): boolean {
    return this.openState();
  }

  @HostBinding('class.dropdown')
  readonly baseDropdownClass = true;

  @HostBinding('class.dropdown-open')
  get isDropdownOpen(): boolean {
    return this.openState();
  }

  @HostBinding('class.dropdown-bottom')
  get isPositionedBottom(): boolean {
    return this.hasPositionSegment('bottom');
  }

  @HostBinding('class.dropdown-top')
  get isPositionedTop(): boolean {
    return this.hasPositionSegment('top');
  }

  @HostBinding('class.dropdown-left')
  get isPositionedLeft(): boolean {
    return this.hasPositionSegment('left');
  }

  @HostBinding('class.dropdown-right')
  get isPositionedRight(): boolean {
    return this.hasPositionSegment('right');
  }

  @HostBinding('class.dropdown-start')
  get isPositionedStart(): boolean {
    return this.hasPositionSegment('start');
  }

  @HostBinding('class.dropdown-end')
  get isPositionedEnd(): boolean {
    return this.hasPositionSegment('end');
  }

  @HostListener('click', ['$event'])
  onClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    const hostElement = this.elementRef.nativeElement;
    const triggerElement = target.closest('[trigger]');
    const triggerInsideHost = !!triggerElement && hostElement.contains(triggerElement);

    if (triggerInsideHost) {
      this.setDropdownOpenState(!this.openState());
      return;
    }

    const contentElement = target.closest('[content]');
    if (contentElement && hostElement.contains(contentElement)) {
      this.setDropdownOpenState(false);
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    const clickedInside = this.elementRef.nativeElement.contains(target);
    if (!clickedInside && this.openState()) {
      this.setDropdownOpenState(false);
    }
  }

  private setDropdownOpenState(isOpen: boolean): void {
    if (this.openState() === isOpen) {
      if (!isOpen) {
        this.blurActiveElementWithinDropdown();
      }
      return;
    }

    this.openState.set(isOpen);

    if (!isOpen) {
      this.blurActiveElementWithinDropdown();
    }
  }

  private blurActiveElementWithinDropdown(): void {
    if (typeof document === 'undefined') {
      return;
    }

    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLElement &&
      this.elementRef.nativeElement.contains(activeElement)
    ) {
      activeElement.blur();
    }
  }

  private hasPositionSegment(segment: DropdownPositionSegment): boolean {
    return this.positionSegments().has(segment);
  }

  private coerceBoolean(value: boolean | string | null | undefined): boolean {
    if (typeof value === 'string') {
      const normalized = value.trim().toLowerCase();
      if (normalized === '' || normalized === 'true') {
        return true;
      }
      if (normalized === 'false') {
        return false;
      }
    }

    return !!value;
  }

  private isValidPositionSegment(value: string): value is DropdownPositionSegment {
    return ['bottom', 'top', 'left', 'right', 'start', 'end'].includes(
      value as DropdownPositionSegment,
    );
  }
}
