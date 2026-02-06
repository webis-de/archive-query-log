import { Signal, WritableSignal } from '@angular/core';
import { SuggestionsService, Suggestion } from '../services/suggestions.service';

interface SearchSuggestionsOptions {
  suggestionsService: SuggestionsService;
  suggestions: Signal<Suggestion[]>;
  getQuery: () => string;
  setQuery: (value: string) => void;
  showSuggestions: WritableSignal<boolean>;
  onSearch: () => void;
}

export const createSearchSuggestionsController = (options: SearchSuggestionsOptions) => {
  const { suggestionsService, suggestions, getQuery, setQuery, showSuggestions, onSearch } =
    options;

  const onSearchInput = (value: string): void => {
    setQuery(value);
    const trimmedValue = value.trim();
    if (trimmedValue.length >= suggestionsService.MINIMUM_QUERY_LENGTH) {
      suggestionsService.search(trimmedValue);
      showSuggestions.set(true);
    } else {
      suggestionsService.search('');
      showSuggestions.set(false);
    }
  };

  const onSuggestionSelect = (suggestion: Suggestion): void => {
    setQuery(suggestion.query);
    showSuggestions.set(false);
    onSearch();
  };

  const onSearchFocus = (): void => {
    if (
      suggestions().length > 0 &&
      getQuery().trim().length >= suggestionsService.MINIMUM_QUERY_LENGTH
    ) {
      showSuggestions.set(true);
    }
  };

  return {
    onSearchInput,
    onSuggestionSelect,
    onSearchFocus,
  };
};
