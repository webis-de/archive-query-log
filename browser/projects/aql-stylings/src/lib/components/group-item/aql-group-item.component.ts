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

  onToggle(): void {
    this.open.update(v => !v);
  }

  onSummaryKeydown(event: KeyboardEvent): void {
    const target = event.target as HTMLElement | null;
    if (!target) {
      return;
    }

    // Prevent Space/Enter from toggling when inside input field
    const inputField = target.closest('aql-input-field');
    const input = target.closest('input');
    if (inputField || input) {
      event.stopPropagation();
      return;
    }

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      this.onToggle();
    }
  }
}
