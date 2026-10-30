import { components } from '../api/schema';

/**
 * Archive response from the archives API endpoints
 */
export type ArchiveResponse = components['schemas']['EnrichedArchive'];

/**
 * Simplified archive option for dropdowns and lists
 */
export interface ArchiveDetail {
  id: string;
  name: string;
  cdx_api_url?: string;
  serp_count?: number;
  memento_api_url?: string;
  homepage?: string;
}
