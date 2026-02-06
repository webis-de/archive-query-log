import { Location } from '@angular/common';
import { WritableSignal } from '@angular/core';

export interface PanelNavigationOptions {
  location: Location;
  basePath: string;
  getSearchQuery: () => string;
  isPanelOpen: WritableSignal<boolean>;
}

export interface PanelNavigationController {
  navigateToItem: (itemId: string) => void;
  closePanel: () => void;
}

/**
 * Creates a controller for panel navigation with URL synchronization.
 * Uses Location.go() to update URL without triggering Angular route navigation,
 * preventing component recreation when toggling detail panels.
 */
export const createPanelNavigationController = (
  options: PanelNavigationOptions,
): PanelNavigationController => {
  const { location, basePath, getSearchQuery, isPanelOpen } = options;

  const buildQueryString = (): string => {
    const queryParams = new URLSearchParams(window.location.search);
    return queryParams.toString();
  };

  const navigateToItem = (itemId: string): void => {
    const encodedId = encodeURIComponent(itemId);
    const queryString = buildQueryString();
    location.go(`${basePath}/${encodedId}${queryString ? '?' + queryString : ''}`);
    isPanelOpen.set(true);
  };

  const closePanel = (): void => {
    const queryParams = new URLSearchParams(window.location.search);
    queryParams.set('q', getSearchQuery());
    const queryString = queryParams.toString();
    location.go(`${basePath}${queryString ? '?' + queryString : ''}`);
    isPanelOpen.set(false);
  };

  return { navigateToItem, closePanel };
};
