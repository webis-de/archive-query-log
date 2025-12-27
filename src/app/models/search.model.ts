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
  archive: Archive;
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
}

export interface SearchParams {
  query: string;
  size?: number;
  provider_id?: string;
  year?: number;
  status_code?: number;
}
