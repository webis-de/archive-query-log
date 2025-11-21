import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'aql-menu-item',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-menu-item.component.html',
  styleUrl: './aql-menu-item.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlMenuItemComponent {
  readonly iconBefore = input<string | null>(null);
  readonly iconAfter = input<string | null>(null);
  readonly interactive = input(true, {
    transform: (v: boolean | string) => v !== 'false' && v !== false,
  });
  readonly selected = input<boolean>(false);
  readonly selectedChange = output<boolean>();

  onItemClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    const afterSlot = target.closest('.after-slot');

    if (afterSlot) {
      return;
    }
  }

  onMainFocus(): void {
    if (this.interactive()) {
      this.selectedChange.emit(true);
    }
  }

  onAfterClick(event: MouseEvent): void {
    event.preventDefault();
  }

  onAfterMouseDown(event: MouseEvent, element: HTMLElement): void {
    event.stopPropagation();
    event.preventDefault();
    element.blur();
  }
}
