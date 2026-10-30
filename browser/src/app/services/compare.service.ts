import { Injectable, signal, computed, inject } from '@angular/core';
import {
  CompareResponse,
  SearchResultWithOrganicResults,
  SerpComparisonResult,
} from '../models/search.model';
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

  /**
   * Compute URL overlaps, rankings, and similarity metrics from the compared SERPs and their organic results.
   */
  mapApiResponse(apiResponse: SerpComparisonResult): CompareResponse {
    const serps: Record<string, SearchResultWithOrganicResults> = {};
    const urlRanks: Record<string, Map<string, number>> = {};
    for (const serp of apiResponse.serps) {
      serps[serp._id] = serp;
      const ranks = new Map<string, number>();
      for (const result of serp.results ?? []) {
        if (result.url && !ranks.has(result.url)) {
          ranks.set(result.url, result.rank);
        }
      }
      urlRanks[serp._id] = ranks;
    }
    const serpIds = Object.keys(serps);

    const urlSets = serpIds.map(id => new Set(urlRanks[id].keys()));
    const common = serpIds.length
      ? [...urlSets[0]].filter(url => urlSets.every(urls => urls.has(url)))
      : [];
    const commonSet = new Set(common);

    const unique_urls: Record<string, string[]> = {};
    const total_urls: Record<string, number> = {};
    serpIds.forEach((id, index) => {
      unique_urls[id] = [...urlSets[index]].filter(url => !commonSet.has(url));
      total_urls[id] = urlSets[index].size;
    });

    const jaccard: Record<string, Record<string, number>> = {};
    const spearman: Record<string, Record<string, number>> = {};
    for (const id1 of serpIds) {
      jaccard[id1] = {};
      spearman[id1] = {};
      for (const id2 of serpIds) {
        if (id1 === id2) {
          jaccard[id1][id2] = 1.0;
          spearman[id1][id2] = 1.0;
        } else {
          jaccard[id1][id2] = jaccardSimilarity(urlRanks[id1], urlRanks[id2]);
          spearman[id1][id2] = spearmanCorrelation(urlRanks[id1], urlRanks[id2]);
        }
      }
    }

    const rankings: Record<string, Record<string, number>> = {};
    for (const url of common) {
      rankings[url] = {};
      for (const id of serpIds) {
        rankings[url][id] = urlRanks[id].get(url) as number;
      }
    }

    const providers: Record<string, string> = {};
    const timestamps: Record<string, string> = {};
    const queries: Record<string, string> = {};
    const archives: Record<string, string> = {};
    const status_codes: Record<string, number | null> = {};
    for (const [id, serp] of Object.entries(serps)) {
      providers[id] = serp.provider.domain;
      timestamps[id] = serp.capture.timestamp;
      queries[id] = serp.url_query;
      archives[id] = serp.archive.memento_api_url;
      status_codes[id] = serp.capture.status_code;
    }

    return {
      serps,
      common_urls: common,
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

function jaccardSimilarity(ranks1: Map<string, number>, ranks2: Map<string, number>): number {
  const union = new Set([...ranks1.keys(), ...ranks2.keys()]);
  if (union.size === 0) return 0;
  const intersection = [...ranks1.keys()].filter(url => ranks2.has(url)).length;
  return intersection / union.size;
}

function spearmanCorrelation(ranks1: Map<string, number>, ranks2: Map<string, number>): number {
  const common = [...ranks1.keys()].filter(url => ranks2.has(url));
  const n = common.length;
  if (n < 2) return 0;
  const rankDiffsSquared = common.reduce(
    (sum, url) => sum + ((ranks1.get(url) as number) - (ranks2.get(url) as number)) ** 2,
    0,
  );
  return 1 - (6 * rankDiffsSquared) / (n * (n ** 2 - 1));
}
