import { Component, computed, input, output } from '@angular/core';

import { CommonModule } from '@angular/common';

import { TranslateModule } from '@ngx-translate/core';

import { AqlButtonComponent } from '../button/aql-button.component';

import { AqlDropdownComponent } from '../dropdown/aql-dropdown.component';

import { AqlTooltipDirective } from '../../directives/tooltip/tooltip.directive';

export type PaginationSize = 'xs' | 'sm' | 'md' | 'lg';

@Component({
  selector: 'aql-pagination',

  standalone: true,

  imports: [
    CommonModule,

    TranslateModule,

    AqlButtonComponent,

    AqlDropdownComponent,

    AqlTooltipDirective,
  ],

  templateUrl: './aql-pagination.component.html',

  styleUrls: ['./aql-pagination.component.css'],
})
export class AqlPaginationComponent {
  readonly totalItems = input.required<number>();

  readonly pageSize = input<number>(10);

  readonly currentPage = input<number>(1);

  readonly maxVisiblePages = input<number>(3);

  readonly size = input<PaginationSize>('md');

  readonly showPageSizeSelector = input<boolean>(false);

  readonly pageSizeOptions = input<number[]>([10, 20, 50]);

  readonly contentMaxWidth = input<string | null>(null);

  readonly contentClass = input<string | string[] | Set<string> | Record<string, unknown> | null>(
    null,
  );

  readonly showSelectorLabel = input<boolean>(true);

  readonly pageChange = output<number>();

  readonly pageSizeChange = output<number>();

  readonly selectedPageSize = computed(() => this.pageSize());

  readonly totalPages = computed(() => {
    const total = Math.ceil(this.totalItems() / this.pageSize());

    return total > 0 ? total : 1;
  });

  readonly visiblePages = computed(() => {
    const total = this.totalPages();

    const current = this.currentPage();

    const max = this.maxVisiblePages();

    if (total <= max) {
      return Array.from({ length: total }, (_, i) => i + 1);
    }

    const half = Math.floor(max / 2);

    let start = Math.max(1, current - half);

    const end = Math.min(total, start + max - 1);

    if (end - start + 1 < max) {
      start = Math.max(1, end - max + 1);
    }

    const pages: (number | 'ellipsis-start' | 'ellipsis-end')[] = [];

    if (start > 1) {
      pages.push(1);

      if (start > 2) {
        pages.push('ellipsis-start');
      }
    }

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (end < total) {
      if (end < total - 1) {
        pages.push('ellipsis-end');
      }

      pages.push(total);
    }

    return pages;
  });

  readonly isFirstPage = computed(() => this.currentPage() === 1);

  readonly isLastPage = computed(() => this.currentPage() === this.totalPages());

  readonly startItem = computed(() => {
    return (this.currentPage() - 1) * this.pageSize() + 1;
  });

  readonly endItem = computed(() => {
    return Math.min(this.currentPage() * this.pageSize(), this.totalItems());
  });

  goToPage(page: number): void {
    if (page >= 1 && page <= this.totalPages() && page !== this.currentPage()) {
      this.pageChange.emit(page);
    }
  }

  goToPreviousPage(): void {
    if (!this.isFirstPage()) {
      this.goToPage(this.currentPage() - 1);
    }
  }

  goToNextPage(): void {
    if (!this.isLastPage()) {
      this.goToPage(this.currentPage() + 1);
    }
  }

  onPageSizeSelect(newSize: number): void {
    this.pageSizeChange.emit(newSize);

    // Reset to first page when page size changes

    if (this.currentPage() !== 1) {
      this.pageChange.emit(1);
    }
  }

  isPageNumber(page: number | 'ellipsis-start' | 'ellipsis-end'): page is number {
    return typeof page === 'number';
  }

  trackByPage(_index: number, page: number | 'ellipsis-start' | 'ellipsis-end'): number | string {
    return typeof page === 'number' ? page : page;
  }
}
