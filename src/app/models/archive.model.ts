/**
 * Archive response from the archives list endpoint
 */
export interface ArchiveResponse {
  id: string;
  name: string;
  memento_api_url?: string;
  cdx_api_url?: string;
  homepage?: string;
  serp_count?: number;
}

/**
 * Response from the archives list API endpoint
 */
export interface ArchivesApiResponse {
  total: number;
  archives: ArchiveResponse[];
}

/**
 * Simplified archive option for dropdowns and lists
 */
export interface ArchiveDetail {
  id: string;
  name: string;
  cdx_api_url?: string;
  serp_count?: number;
  memento_api_url?: string;
}

/**
 * Response from the archive detail API endpoint
 */
export interface ArchiveDetailResponse {
  archive: {
    id: string;
    name: string;
    cdx_api_url?: string;
    memento_api_url?: string;
    homepage?: string;
    serp_count?: number;
  };
}
