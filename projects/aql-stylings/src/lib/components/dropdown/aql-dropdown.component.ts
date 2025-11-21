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
  PLATFORM_ID,
  OnDestroy,
  ViewChild,
} from '@angular/core';
import { CommonModule, isPlatformBrowser } from '@angular/common';

type DropdownPositionSegment = 'bottom' | 'top' | 'left' | 'right' | 'start' | 'end';
export type DropdownPosition =
  | DropdownPositionSegment
  | `${DropdownPositionSegment} ${DropdownPositionSegment}`;

@Component({
  selector: 'aql-dropdown',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-dropdown.component.html',
  styleUrl: './aql-dropdown.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlDropdownComponent implements OnDestroy {
  private readonly elementRef = inject(ElementRef<HTMLElement>);
  private readonly platformId = inject(PLATFORM_ID);

  @ViewChild('contentElement') contentElement!: ElementRef<HTMLElement>;

  readonly matchTriggerWidth = input(false, { transform: booleanAttribute });
  readonly contentWidth = input<string | null>('14rem');
  readonly position = input<DropdownPosition | undefined>('bottom');

  private readonly openState = signal(false);
  protected readonly fixedStyles = signal<Record<string, string | number>>({});
  private cleanupFn: (() => void) | null = null;

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
  }

  onContentClick(event: MouseEvent): void {
    // Close dropdown and stop propagation to prevent group item from closing
    this.setDropdownOpenState(false);
    event.stopPropagation();
    event.preventDefault();
  }

  onContentMouseDown(event: MouseEvent): void {
    // Prevent parent menu items from receiving :active styles
    event.stopPropagation();
    event.preventDefault();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    if (this.contentElement && this.contentElement.nativeElement.contains(target)) {
      return;
    }

    const clickedInside = this.elementRef.nativeElement.contains(target);

    if (!clickedInside && this.openState()) {
      this.setDropdownOpenState(false);
    }
  }

  ngOnDestroy(): void {
    this.cleanupListeners();
    if (this.openState() && isPlatformBrowser(this.platformId) && this.contentElement) {
      if (this.contentElement.nativeElement.parentElement === document.body) {
        document.body.removeChild(this.contentElement.nativeElement);
      }
    }
  }

  @HostListener('window:resize', ['$event'])
  onWindowResize(): void {
    if (this.openState()) {
      this.updateFixedPosition();
    }
  }

  private setDropdownOpenState(isOpen: boolean): void {
    if (this.openState() === isOpen) {
      if (!isOpen) {
        this.blurActiveElementWithinDropdown();
      }
      return;
    }

    if (isOpen) {
      this.updateFixedPosition();
      this.moveContentToBody();
      this.setupListeners();
      this.openState.set(isOpen);
    } else {
      this.openState.set(isOpen);
      requestAnimationFrame(() => {
        this.restoreContent();
      });
      this.cleanupListeners();
    }

    if (!isOpen) {
      this.blurActiveElementWithinDropdown();
    }
  }

  private moveContentToBody(): void {
    if (isPlatformBrowser(this.platformId) && this.contentElement) {
      document.body.appendChild(this.contentElement.nativeElement);
    }
  }

  private restoreContent(): void {
    if (isPlatformBrowser(this.platformId) && this.contentElement) {
      this.elementRef.nativeElement.appendChild(this.contentElement.nativeElement);
    }
  }

  private setupListeners(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }

    const scrollHandler = () => {
      this.updateFixedPosition();
    };

    window.addEventListener('scroll', scrollHandler, { capture: true, passive: true });

    this.cleanupFn = () => {
      window.removeEventListener('scroll', scrollHandler, { capture: true });
    };
  }

  private cleanupListeners(): void {
    if (this.cleanupFn) {
      this.cleanupFn();
      this.cleanupFn = null;
    }
  }

  private updateFixedPosition(): void {
    if (!isPlatformBrowser(this.platformId)) {
      return;
    }

    const rect = this.elementRef.nativeElement.getBoundingClientRect();
    const styles: Record<string, string | number> = {
      position: 'fixed',
      zIndex: '9999',
    };

    const segments = this.positionSegments();
    const isRight = segments.has('right');
    const isLeft = segments.has('left');
    const isTop = segments.has('top');
    const isBottom = !isTop && !isLeft && !isRight;
    const isEnd = segments.has('end');
    const margin = 4;

    // Vertical alignment
    if (isBottom) {
      styles['top'] = `${rect.bottom + margin}px`;
      if (isEnd) {
        styles['right'] = `${window.innerWidth - rect.right}px `;
      } else {
        styles['left'] = `${rect.left}px `;
      }
    } else if (isTop) {
      styles['bottom'] = `${window.innerHeight - rect.top + margin}px`;
      if (isEnd) {
        styles['right'] = `${window.innerWidth - rect.right}px`;
      } else {
        styles['left'] = `${rect.left}px`;
      }
    }

    // Horizontal alignment
    if (isRight) {
      styles['left'] = `${rect.right + margin}px`;
      if (isEnd) {
        styles['bottom'] = `${window.innerHeight - rect.bottom}px`;
      } else {
        styles['top'] = `${rect.top}px`;
      }
    } else if (isLeft) {
      styles['right'] = `${window.innerWidth - rect.left + margin}px`;
      if (isEnd) {
        styles['bottom'] = `${window.innerHeight - rect.bottom}px`;
      } else {
        styles['top'] = `${rect.top}px`;
      }
    }

    this.fixedStyles.set(styles);
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
