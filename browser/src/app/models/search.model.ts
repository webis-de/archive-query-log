import { components, operations } from '../api/schema';

type Schemas = components['schemas'];

export type Archive = Schemas['InnerArchive'];
export type Provider = Schemas['InnerProvider'];
export type Capture = Schemas['InnerCapture'];
export type Parser = Schemas['InnerParser'];
export type WarcLocation = Schemas['WarcLocation'];
export type OrganicResult = Schemas['OrganicResult'];
export type SearchResult = Schemas['EnrichedSerp'];
export type SearchResultWithOrganicResults = Schemas['EnrichedSerpWithResults'];
export type SerpComparisonResult = Schemas['SerpComparisonResult'];
export type ArchiveBucket = Schemas['ArchiveBucket'];
export type ProviderBucket = Schemas['ProviderBucket'];
export type DateHistogramBucket = Schemas['DateHistogramBucket'];
export type QueryBucket = Schemas['QueryBucket'];
export type QuerySuggestion = Schemas['QuerySuggestion'];
export type QuerySuggestions = Schemas['QuerySuggestions'];
export type DateHistogramInterval = NonNullable<
  NonNullable<operations['serp_date_histogram']['parameters']['query']>['interval']
>;

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  did_you_mean: QuerySuggestion[];
}

export interface SearchParams {
  query: string;
  size?: number;
  provider_id?: string;
  year?: number;
  status_code?: number;
  advanced_mode?: boolean;
  fuzzy?: boolean;
}

export interface QueryHistogramBucket {
  date: string;
  count: number;
}

export interface TopQueryItem {
  query: string;
  count: number;
}

export interface TopProviderItem {
  provider: string;
  count: number;
}

export interface TopArchiveItem {
  archive: string;
  count: number;
}

export interface QueryMetadataResponse {
  query: string;
  total_hits: number;
  top_queries: TopQueryItem[];
  date_histogram: QueryHistogramBucket[];
  top_providers: TopProviderItem[];
  top_archives: TopArchiveItem[];
}

export interface QueryMetadataParams {
  query: string;
  top_n_queries?: number;
  interval?: DateHistogramInterval;
  top_providers?: number;
  top_archives?: number;
  last_n_months?: number;
  provider_id?: string;
}

// Unfurl data
export interface UnfurlData {
  scheme: string;
  netloc: string;
  port: number | null;
  path: string;
  path_segments: string[];
  query_parameters: Record<string, string | string[]>;
  fragment: string | null;
}

// Unbranded SERP
export interface UnbrandedResult {
  position: number;
  url: string;
  title: string | null;
  snippet: string | null;
}

export interface UnbrandedQuery {
  raw: string;
  parsed: string | null;
}

export interface UnbrandedMetadata {
  timestamp: string;
  url: string;
  status_code: number | null;
}

export interface UnbrandedSerp {
  serp_id: string;
  query: UnbrandedQuery;
  results: UnbrandedResult[];
  metadata: UnbrandedMetadata;
}

export interface SerpDetailsResponse {
  serp_id: string;
  serp: SearchResult;
  related: SearchResult[];
  unfurl: UnfurlData | null;
  unfurl_web: string;
}

export interface CompareResponse {
  serps: Record<string, SearchResultWithOrganicResults>;
  common_urls: string[];
  unique_urls: Record<string, string[]>;
  rankings: Record<string, Record<string, number>>;
  similarity: {
    jaccard: Record<string, Record<string, number>>;
    spearman: Record<string, Record<string, number>>;
  };
  metadata_comparison: {
    providers: Record<string, string>;
    timestamps: Record<string, string>;
    queries: Record<string, string>;
    archives: Record<string, string>;
    status_codes: Record<string, number | null>;
    total_urls: Record<string, number>;
  };
}
