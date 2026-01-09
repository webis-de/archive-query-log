import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostBinding,
  HostListener,
  booleanAttribute,
  computed,
  inject,
  input,
  output,
  signal,
  PLATFORM_ID,
  OnDestroy,
  viewChild,
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

  // Track currently open dropdown globally
  private static currentlyOpenDropdown: AqlDropdownComponent | null = null;

  readonly contentElement = viewChild<ElementRef<HTMLElement>>('contentElement');

  readonly matchTriggerWidth = input(false, { transform: booleanAttribute });
  readonly contentWidth = input<string | null>('14rem');
  readonly position = input<DropdownPosition | undefined>('bottom');
  readonly open = input<boolean | undefined>(undefined);
  readonly openChange = output<boolean>();

  readonly internalOpen = signal(false);
  protected readonly fixedStyles = signal<Record<string, string | number>>({});
  private cleanupFn: (() => void) | null = null;

  // Use external open if provided, otherwise use internal state
  readonly isOpen = computed(() => {
    const external = this.open();
    return external !== undefined ? external : this.internalOpen();
  });

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

  @HostBinding('class.dropdown')
  readonly baseDropdownClass = true;

  @HostBinding('class.dropdown-open')
  get isDropdownOpen(): boolean {
    return this.isOpen();
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
      this.setDropdownOpenState(!this.isOpen());
      return;
    }
  }

  onContentClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const closable = target.closest('aql-menu-item, a, button, [closeDropdown]');

    if (closable) {
      this.setDropdownOpenState(false);
    }

    event.stopPropagation();
  }

  onContentMouseDown(event: MouseEvent): void {
    // Prevent parent menu items from receiving :active styles
    event.stopPropagation();
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.isOpen()) {
      return;
    }

    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    const contentEl = this.contentElement();
    const clickedInContent = contentEl && contentEl.nativeElement.contains(target);
    const clickedInTrigger = this.elementRef.nativeElement.contains(target);

    // If clicked outside both trigger and content, close the dropdown
    if (!clickedInTrigger && !clickedInContent) {
      this.setDropdownOpenState(false);
    }
  }

  ngOnDestroy(): void {
    this.cleanupListeners();
    if (AqlDropdownComponent.currentlyOpenDropdown === this) {
      AqlDropdownComponent.currentlyOpenDropdown = null;
    }
    const contentEl = this.contentElement();
    if (this.isOpen() && isPlatformBrowser(this.platformId) && contentEl) {
      if (contentEl.nativeElement.parentElement === document.body) {
        document.body.removeChild(contentEl.nativeElement);
      }
    }
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    if (this.isOpen()) {
      this.updateFixedPosition();
    }
  }

  private setDropdownOpenState(isOpen: boolean): void {
    if (this.isOpen() === isOpen) {
      if (!isOpen) {
        this.blurActiveElementWithinDropdown();
      }
      return;
    }

    if (isOpen) {
      // Close any other currently open dropdown
      if (
        AqlDropdownComponent.currentlyOpenDropdown &&
        AqlDropdownComponent.currentlyOpenDropdown !== this
      ) {
        AqlDropdownComponent.currentlyOpenDropdown.setDropdownOpenState(false);
      }

      this.updateFixedPosition();
      this.moveContentToBody();
      this.setupListeners();
      this.internalOpen.set(isOpen);
      this.openChange.emit(isOpen);

      // Register this dropdown as currently open
      AqlDropdownComponent.currentlyOpenDropdown = this;
    } else {
      this.internalOpen.set(isOpen);
      this.openChange.emit(isOpen);
      requestAnimationFrame(() => {
        this.restoreContent();
      });
      this.cleanupListeners();

      // Unregister if this were the open dropdown
      if (AqlDropdownComponent.currentlyOpenDropdown === this) {
        AqlDropdownComponent.currentlyOpenDropdown = null;
      }
    }

    if (!isOpen) {
      this.blurActiveElementWithinDropdown();
    }
  }

  private moveContentToBody(): void {
    const contentEl = this.contentElement();
    if (isPlatformBrowser(this.platformId) && contentEl) {
      document.body.appendChild(contentEl.nativeElement);
    }
  }

  private restoreContent(): void {
    const contentEl = this.contentElement();
    if (isPlatformBrowser(this.platformId) && contentEl) {
      this.elementRef.nativeElement.appendChild(contentEl.nativeElement);
      contentEl.nativeElement.style.position = '';
      contentEl.nativeElement.style.zIndex = '';
      contentEl.nativeElement.style.top = '';
      contentEl.nativeElement.style.bottom = '';
      contentEl.nativeElement.style.left = '';
      contentEl.nativeElement.style.right = '';
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

    // Manually apply styles to the element to ensure it is positioned correctly
    const contentEl = this.contentElement();
    if (contentEl) {
      contentEl.nativeElement.style.top = '';
      contentEl.nativeElement.style.bottom = '';
      contentEl.nativeElement.style.left = '';
      contentEl.nativeElement.style.right = '';

      Object.entries(styles).forEach(([key, value]) => {
        contentEl.nativeElement.style.setProperty(
          key.replace(/[A-Z]/g, m => '-' + m.toLowerCase()),
          value.toString(),
        );
      });
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

  private isValidPositionSegment(value: string): value is DropdownPositionSegment {
    return ['bottom', 'top', 'left', 'right', 'start', 'end'].includes(
      value as DropdownPositionSegment,
    );
  }
}
