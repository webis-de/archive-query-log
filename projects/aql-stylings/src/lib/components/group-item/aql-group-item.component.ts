import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AqlMenuItemComponent } from '../menu-item/aql-menu-item.component';

@Component({
  selector: 'aql-group-item',
  standalone: true,
  imports: [CommonModule, AqlMenuItemComponent],
  templateUrl: './aql-group-item.component.html',
  styleUrl: './aql-group-item.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlGroupItemComponent {
  readonly iconBefore = input<string | null>(null);
  readonly iconBeforeOpen = input<string | null>(null);
  readonly open = signal(false);
  readonly computedIconBefore = computed(() => {
    const icon = this.iconBefore();
    const iconOpen = this.iconBeforeOpen();
    if (!icon) return null;
    return this.open() && iconOpen ? iconOpen : icon;
  });

  onToggle(event: Event): void {
    const details = event.target as HTMLDetailsElement | null;
    this.open.set(!!details?.open);
  }

  onSummaryClick(event: MouseEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    // Check if click is on the [after] slot
    const afterSlot = target.closest('.after-slot');
    if (afterSlot) {
      event.preventDefault();
      return;
    }
  }
}
