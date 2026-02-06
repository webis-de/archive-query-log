import { Injectable, signal, computed, inject } from '@angular/core';
import { CompareApiResponse, CompareResponse, SearchResult } from '../models/search.model';
import { ToastService } from 'aql-stylings';
import { TranslateService } from '@ngx-translate/core';

@Injectable({
  providedIn: 'root',
})
export class CompareService {
  readonly selectedSerpIds = signal<string[]>([]);
  readonly maxItems = 5;
  readonly canCompare = computed(() => {
    const count = this.selectedSerpIds().length;
    return count >= 2 && count <= this.maxItems;
  });
  readonly isFull = computed(() => this.selectedSerpIds().length >= this.maxItems);

  private readonly toastService = inject(ToastService);
  private readonly translateService = inject(TranslateService);

  toggle(id: string): void {
    const current = this.selectedSerpIds();
    if (current.includes(id)) {
      this.remove(id);
    } else {
      this.add(id);
    }
  }

  add(id: string): void {
    const current = this.selectedSerpIds();
    if (current.length >= this.maxItems) {
      const message = this.translateService.instant('compare.maxItemsReached', {
        max: this.maxItems,
      });
      this.toastService.show(message, 'warning');
      return;
    }
    if (!current.includes(id)) {
      this.selectedSerpIds.update(ids => [...ids, id]);
    }
  }

  remove(id: string): void {
    this.selectedSerpIds.update(ids => ids.filter(itemId => itemId !== id));
  }

  clear(): void {
    this.selectedSerpIds.set([]);
  }

  isSelected(id: string): boolean {
    return this.selectedSerpIds().includes(id);
  }

  mapApiResponse(apiResponse: CompareApiResponse): CompareResponse {
    const serps: Record<string, SearchResult> = {};
    apiResponse.serps_full_data.forEach(item => {
      serps[item.serp_id] = item.data;
    });

    const unique_urls: Record<string, string[]> = {};
    apiResponse.url_comparison.unique_per_serp.forEach(item => {
      unique_urls[item.serp_id] = item.unique_urls;
    });

    const jaccard: Record<string, Record<string, number>> = {};
    const spearman: Record<string, Record<string, number>> = {};

    // Initialize matrices
    apiResponse.comparison_summary.serp_ids.forEach(id1 => {
      jaccard[id1] = {};
      spearman[id1] = {};
      apiResponse.comparison_summary.serp_ids.forEach(id2 => {
        if (id1 === id2) {
          jaccard[id1][id2] = 1.0;
          spearman[id1][id2] = 1.0;
        }
      });
    });

    apiResponse.similarity_metrics.pairwise_jaccard.forEach(pair => {
      if (!jaccard[pair.serp_1]) jaccard[pair.serp_1] = {};
      if (!jaccard[pair.serp_2]) jaccard[pair.serp_2] = {};
      jaccard[pair.serp_1][pair.serp_2] = pair.jaccard_similarity;
      jaccard[pair.serp_2][pair.serp_1] = pair.jaccard_similarity;
    });

    apiResponse.similarity_metrics.pairwise_spearman.forEach(pair => {
      if (!spearman[pair.serp_1]) spearman[pair.serp_1] = {};
      if (!spearman[pair.serp_2]) spearman[pair.serp_2] = {};
      spearman[pair.serp_1][pair.serp_2] = pair.spearman_correlation;
      spearman[pair.serp_2][pair.serp_1] = pair.spearman_correlation;
    });

    const providers: Record<string, string> = {};
    const timestamps: Record<string, string> = {};
    const queries: Record<string, string> = {};
    const archives: Record<string, string> = {};
    const status_codes: Record<string, number> = {};
    const total_urls: Record<string, number> = {};

    apiResponse.serps_metadata.forEach(meta => {
      const full = serps[meta.serp_id];
      providers[meta.serp_id] = full?._source.provider.domain || meta.provider_id;
      timestamps[meta.serp_id] = meta.timestamp;
      queries[meta.serp_id] = meta.query;
      archives[meta.serp_id] = meta.archive;
      status_codes[meta.serp_id] = meta.status_code;
    });

    apiResponse.url_comparison.url_counts.forEach(count => {
      total_urls[count.serp_id] = count.total_urls;
    });

    const rankings: Record<string, Record<string, number>> = {};
    if (apiResponse.ranking_comparison && Array.isArray(apiResponse.ranking_comparison)) {
      apiResponse.ranking_comparison.forEach(item => {
        if (item.url && item.ranks) {
          rankings[item.url] = item.ranks;
        }
      });
    }

    return {
      serps,
      common_urls: apiResponse.url_comparison.common_urls,
      unique_urls,
      rankings,
      similarity: {
        jaccard,
        spearman,
      },
      metadata_comparison: {
        providers,
        timestamps,
        queries,
        archives,
        status_codes,
        total_urls,
      },
    };
  }
}
