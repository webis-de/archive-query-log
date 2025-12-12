import {
  ChangeDetectionStrategy,
  Component,
  input,
  output,
  computed,
  booleanAttribute,
} from '@angular/core';
import { CommonModule } from '@angular/common';

export type TabSize = 'xs' | 'sm' | 'md' | 'lg';
export type TabStyle = 'default' | 'border' | 'lift' | 'box';

export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
  badge?: string | number;
  icon?: string;
}

@Component({
  selector: 'aql-tab-menu',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './aql-tab-menu.component.html',
  styleUrl: './aql-tab-menu.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AqlTabMenuComponent {
  readonly tabs = input.required<TabItem[]>();
  readonly activeTabId = input<string | null>(null);
  readonly size = input<TabSize>('md');
  readonly tabStyle = input<TabStyle>('default');
  readonly fullWidth = input(false, { transform: booleanAttribute });

  readonly tabChange = output<string>();

  readonly tabClasses = computed(() => {
    const classes: string[] = ['tabs'];

    const style = this.tabStyle();
    if (style !== 'default') {
      classes.push(`tabs-${style}`);
    }

    const size = this.size();
    if (size !== 'md') {
      classes.push(`tabs-${size}`);
    }

    return classes.join(' ');
  });

  getTabClasses(tab: TabItem): string {
    const classes: string[] = ['tab'];

    if (tab.id === this.activeTabId()) {
      classes.push('tab-active');
    }

    if (tab.disabled) {
      classes.push('tab-disabled');
    }

    return classes.join(' ');
  }

  onTabClick(tab: TabItem): void {
    if (!tab.disabled) {
      this.tabChange.emit(tab.id);
    }
  }
}
