export interface DateHistogramItem {
  date: string;
  count: number;
}

export interface TopEntityItem {
  /** Provider UUID (resolved to the provider's name for display). */
  provider?: string;
  /** Archive name. */
  archive?: string;
  count: number;
}

export interface BaseStatistics {
  archive_id?: string;
  provider_id?: string;
  serp_count: number;
  unique_queries_count: number;
  date_histogram: DateHistogramItem[];
}

export interface ArchiveStatistics extends BaseStatistics {
  top_providers: TopEntityItem[];
}

export interface ProviderStatistics extends BaseStatistics {
  top_archives?: TopEntityItem[];
}
