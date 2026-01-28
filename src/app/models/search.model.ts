export interface Archive {
  id: string;
  cdx_api_url: string;
  memento_api_url: string;
  priority: number;
}

export interface Provider {
  id: string;
  domain: string;
  url_path_prefix: string;
  priority: number;
}

export interface Capture {
  id: string;
  url: string;
  timestamp: string;
  status_code: number;
  digest: string;
  mimetype: string;
}

export interface Parser {
  id?: string;
  should_parse: boolean;
  last_parsed?: string;
}

export interface WarcLocation {
  file: string;
  offset: number;
  length: number;
}

export interface WarcDownloader {
  should_download: boolean;
  id: string;
  last_downloaded: string;
}

export interface SearchResultSource {
  last_modified: string;
  archive?: Archive;
  provider: Provider;
  capture: Capture;
  url_query: string;
  url_query_parser: Parser;
  url_page_parser: Parser;
  url_offset_parser: Parser;
  warc_query_parser: Parser;
  warc_snippets_parser: Parser;
  warc_location?: WarcLocation;
  warc_downloader?: WarcDownloader;
}

export interface SearchResult {
  _index: string;
  _type: string;
  _id: string;
  _score: number;
  _source: SearchResultSource;
}

export interface SearchResponse {
  query: string;
  count: number;
  total: number;
  page_size: number;
  total_pages: number;
  results: SearchResult[];
  pagination: {
    current_results: number;
    total_results: number;
    results_per_page: number;
    total_pages: number;
  };
  fuzzy: boolean;
  fuzziness: string | null;
  expand_synonyms: boolean;
  did_you_mean?: { text: string; score: number }[];
}

export interface SearchParams {
  query: string;
  size?: number;
  provider_id?: string;
  year?: number;
  status_code?: number;
  advanced_mode?: boolean;
  fuzzy?: boolean;
  fuzziness?: 'AUTO' | '0' | '1' | '2';
  expand_synonyms?: boolean;
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

// Generic type for backward compatibility
export interface QueryAggregateItem {
  key?: string;
  label?: string;
  name?: string;
  domain?: string;
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
  interval?: string;
  top_providers?: number;
  top_archives?: number;
  last_n_months?: number;
}

export interface RelatedSerp {
  _id: string;
  _score: number;
  _source: SearchResultSource;
}

// Unfurl data
export interface DomainParts {
  subdomain: string | null;
  domain: string;
  suffix: string;
  registered_domain: string;
}

export interface UnfurlData {
  scheme: string;
  netloc: string;
  port: number | null;
  domain_parts: DomainParts;
  path: string;
  path_segments: string[];
  query_parameters: Record<string, string | string[]>;
  fragment: string | null;
}

// Unbranded SERP
export interface UnbrandedResult {
  position: number;
  url: string;
  title: string;
  snippet: string | null;
}

export interface UnbrandedQuery {
  raw: string;
  parsed: string | null;
}

export interface UnbrandedMetadata {
  timestamp: string;
  url: string;
  status_code: number;
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
  original_url?: string;
  url_without_tracking?: string;
  memento_url?: string;
  related?: {
    count: number;
    serps: RelatedSerp[];
  };
  unfurl?: UnfurlData;
  unfurl_web?: string;
  direct_links_count?: number;
  direct_links?: {
    position: number;
    url: string;
    title: string;
    snippet: string;
  }[];
  unbranded?: UnbrandedSerp;
}
