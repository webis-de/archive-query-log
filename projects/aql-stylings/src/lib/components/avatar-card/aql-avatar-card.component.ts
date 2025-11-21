import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'aql-avatar-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-avatar-card.component.html',
  styleUrl: './aql-avatar-card.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlAvatarCardComponent {
  readonly name = input<string>('Username');
  readonly subtitle = input<string | null>('Institute');
  readonly imageSrc = input<string | null>(null);
  readonly imageAlt = input<string>('Avatar image');
  readonly avatarOnly = input<boolean>(false);

  readonly initials = computed(() => {
    const name = (this.name() ?? '').trim();
    if (!name) {
      return 'A';
    }

    const parts = name.split(/\s+/).filter(Boolean);
    const first = parts[0]?.charAt(0) ?? '';
    const second = parts[1]?.charAt(0) ?? '';

    return `${first}${second}`.toUpperCase() || first.toUpperCase() || 'A';
  });
}
