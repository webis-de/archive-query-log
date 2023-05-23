"""
This script registers the Archive Query Log dataset in ir_datasets.
See: https://github.com/allenai/ir_datasets/
Note: This script is intended to be executed with the Docker image provided.
"""

from pathlib import Path
from typing import NamedTuple, List, Mapping, Optional, Iterator

from ir_datasets import registry
from ir_datasets.datasets.base import Dataset
from ir_datasets.formats import BaseDocs, BaseQueries, BaseQrels, GenericDoc
from ir_datasets.indices import PickleLz4FullStore, Docstore
from pandas import DataFrame, read_json, concat
from tqdm import tqdm

NAME = "archive-query-log"
DATA_DIR = Path('/data/')


def _extract_non_empty_results(serp: Mapping) -> List[dict]:
    if 'serp_results' not in serp or serp['serp_results'] is None:
        return []
    results = []
    for result in serp['serp_results']:
        if ('result_snippet_title' not in result or
                result['result_snippet_title'] is None):
            continue
        results += [result]
    return results


def _parse_serps(base_path: Path, min_results_on_serp: int = 1) -> DataFrame:
    result: DataFrame = concat([
        read_json(path, lines=True)
        for path in tqdm(base_path.glob('serps/part*.gz'), 'Load SERPs')
    ])
    original_length = len(result)
    num_results = result['serp_results'].map(
        lambda serp_results: len(
            _extract_non_empty_results({'serp_results': serp_results})
        )
    )
    mask = num_results >= min_results_on_serp
    result = result[mask]

    print(f'Processed {original_length} SERPs, '
          f'found {len(result)} non-empty SERPs.')

    return result


def _persist_run_file(serps: DataFrame, lang: str = "en") -> None:
    run_data = []
    for _, serp in serps.iterrows():
        results = _extract_non_empty_results(serp)
        max_rank = max(
            result['result_snippet_rank']
            for result in results
        )
        run_data += [
            {
                'query': serp.serp_id,
                'q0': 0,
                'docid': result['result_id'],
                'rank': result['result_snippet_rank'],
                'score': max_rank - result['result_snippet_rank'],
                'system': 'aql'
            }
            for result in results
            if serp['serp_query_text_url_language'] == lang
        ]

    run = DataFrame(run_data)
    run.to_csv(DATA_DIR / 'run.txt', sep=" ", header=False, index=False)


class ArchiveQueryLogQuery(NamedTuple):
    query_id: str
    text: str
    search_provider_name: str
    num_results: int
    lang: str

    def default_text(self):
        return self.text


class ArchiveQueryLogQrel(NamedTuple):
    query_id: str
    doc_id: str
    relevance: int
    iteration: int
    search_provider_name: str
    num_results: int
    lang: str


class ArchiveQueryLogQueries(BaseQueries):
    serps: DataFrame
    lang: Optional[str]

    def __init__(self, serps: DataFrame, lang: Optional[str] = "en"):
        self.serps = serps
        self.lang = lang

    def queries_iter(self) -> Iterator[ArchiveQueryLogQuery]:
        for _, serp in self.serps.iterrows():
            if (self.lang is not None and
                    self.lang != serp["serp_query_text_url_language"]):
                continue
            num_results = len(_extract_non_empty_results(serp))
            if num_results <= 0:
                continue
            yield ArchiveQueryLogQuery(
                query_id=serp["serp_id"],
                text=serp["serp_query_text_html"],
                lang=serp["serp_query_text_url_language"],
                search_provider_name=serp["search_provider_name"],
                num_results=num_results,
            )

    def queries_cls(self):
        return ArchiveQueryLogQuery

    def queries_lang(self) -> Optional[str]:
        return self.lang


class ArchiveQueryLogQrels(BaseQrels):
    serps: DataFrame
    lang: Optional[str]

    def __init__(self, serps: DataFrame, lang: Optional[str] = "en"):
        self.serps = serps
        self.lang = lang

    def qrels_iter(self) -> Iterator[ArchiveQueryLogQrel]:
        for _, serp in self.serps.iterrows():
            if (self.lang is not None and
                    self.lang != serp["serp_query_text_url_language"]):
                continue
            results = _extract_non_empty_results(serp)
            max_rank = max(
                result['result_snippet_rank']
                for result in results
            )
            for result in results:
                yield ArchiveQueryLogQrel(
                    query_id=serp["serp_id"],
                    doc_id=result['result_id'],
                    relevance=max_rank - result['result_snippet_rank'],
                    iteration=0,
                    search_provider_name=serp["search_provider_name"],
                    num_results=len(results),
                    lang=serp["serp_query_text_url_language"],
                )

    def qrels_cls(self):
        return ArchiveQueryLogQrel


class ArchiveQueryLogDocs(BaseDocs):
    serps: DataFrame
    lang: Optional[str]

    def __init__(self, serps: DataFrame, lang: Optional[str] = "en"):
        self.serps = serps
        self.lang = lang

    def docs_iter(self) -> Iterator[GenericDoc]:
        for _, serp in self.serps.iterrows():
            if (self.lang is not None and
                    self.lang != serp["serp_query_text_url_language"]):
                continue
            for result in _extract_non_empty_results(serp):
                yield GenericDoc(
                    doc_id=result['result_id'],
                    text=f"{result['result_snippet_title']} "
                         f"{result['result_snippet_text']}".strip()
                )

    def docs_count(self) -> int:
        return sum(
            len(_extract_non_empty_results(serp))
            for _, serp in self.serps.iterrows()
            if (self.lang is None or
                self.lang == serp["serp_query_text_url_language"])
        )

    def docs_cls(self):
        return GenericDoc

    def docs_lang(self) -> Optional[str]:
        return self.lang

    def docs_store(self) -> Docstore:
        return PickleLz4FullStore(
            path=f'{DATA_DIR}/docs.pklz4',
            init_iter_fn=self.docs_iter,
            data_cls=self.docs_cls(),
            lookup_field='doc_id',
            index_fields=['doc_id'],
        )


_serps = _parse_serps(DATA_DIR)

dataset = Dataset(
    ArchiveQueryLogDocs(_serps),
    ArchiveQueryLogQueries(_serps),
    ArchiveQueryLogQrels(_serps),
)

assert dataset.has_docs(), "dataset has no documents"
assert dataset.has_queries(), "dataset has no queries"

if NAME in registry:
    print(f"Dataset '{NAME}' already registered.")
else:
    registry.register(NAME, dataset)

if __name__ == '__main__':
    _persist_run_file(_serps)
