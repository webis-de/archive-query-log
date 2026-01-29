import { Component, input, output, ChangeDetectionStrategy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { TranslateModule } from '@ngx-translate/core';
import {
  AqlHeaderBarComponent,
  AqlInputFieldComponent,
  AqlButtonComponent,
  AqlDropdownComponent,
  AqlMenuItemComponent,
} from 'aql-stylings';
import { FilterDropdownComponent } from '../filter-dropdown/filter-dropdown.component';
import { FilterState } from '../../models/filter.model';
import { Suggestion } from '../../services/suggestions.service';
import { CompareService } from '../../services/compare.service';

export interface SearchHeaderConfig {
  labelKey: string;
  placeholderKey: string;
  showFilterDropdown?: boolean;
  showSuggestions?: boolean;
  showEntityTabs?: boolean;
  allowComparison?: boolean;
}

@Component({
  selector: 'app-search-header',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    TranslateModule,
    RouterLink,
    AqlHeaderBarComponent,
    AqlInputFieldComponent,
    AqlButtonComponent,
    AqlDropdownComponent,
    AqlMenuItemComponent,
    FilterDropdownComponent,
  ],
  templateUrl: './search-header.component.html',
  styleUrl: './search-header.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SearchHeaderComponent {
  readonly compareService = inject(CompareService);
  readonly searchQuery = input.required<string>();
  readonly config = input.required<SearchHeaderConfig>();
  readonly isPanelOpen = input.required<boolean>();
  readonly isTransitionEnabled = input.required<boolean>();
  readonly isSidebarCollapsed = input<boolean>(false);
  readonly showSuggestionsDropdown = input<boolean>(false);
  readonly suggestions = input<Suggestion[]>([]);
  readonly initialFilters = input<FilterState | null>(null);
  readonly activeFilters = input<string[]>([]);
  readonly searchQueryChange = output<string>();
  readonly searchAction = output<void>();
  readonly searchFocus = output<void>();
  readonly suggestionSelect = output<Suggestion>();
  readonly filtersChanged = output<FilterState>();

  private readonly router = inject(Router);

  onSearchInput(value: string): void {
    this.searchQueryChange.emit(value);
  }

  onSearch(): void {
    this.searchAction.emit();
  }

  onSearchFocus(): void {
    this.searchFocus.emit();
  }

  onSuggestionClick(suggestion: Suggestion): void {
    this.suggestionSelect.emit(suggestion);
  }

  onFiltersChanged(filters: FilterState): void {
    this.filtersChanged.emit(filters);
  }

  navigateToCompare(): void {
    const ids = this.compareService.selectedSerpIds().join(',');
    this.router.navigate([`/serps/compare/${ids}`], { state: { returnUrl: this.router.url } });
  }

  stopPropagation(event: Event): void {
    event.stopPropagation();
  }
}
