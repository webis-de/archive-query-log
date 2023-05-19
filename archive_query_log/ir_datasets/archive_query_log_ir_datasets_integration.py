"""This python file registers new ir_datasets classes for 'archive-query-log'.
   You can find the ir_datasets documentation here: https://github.com/allenai/ir_datasets/.
   This file is intended to work inside the Docker image.
"""
import ir_datasets
from ir_datasets.formats import BaseDocs, BaseQrels, GenericDoc, TrecQueries, TrecQrels, TsvQueries
from typing import NamedTuple, Dict
from ir_datasets.datasets.base import Dataset
from ir_datasets.util import LocalDownload
from ir_datasets.indices import PickleLz4FullStore
from pathlib import Path
from glob import glob
import pandas as pd
from copy import deepcopy

#parse_serps('tira-tutorial/validation-data/')

def extract_non_empty_results(serp):
    if 'serp_results' not in serp or not serp['serp_results']:
        return []
    ret = []
    for result in serp['serp_results']:
        if 'result_snippet_title' not in result or not result['result_snippet_title'] or 'result_snippet_text' not in result or not result['result_snippet_text']:
            continue
        ret += [result]
    return ret

def parse_serps(path, min_results_on_serp = 3):
    ret = pd.concat([pd.read_json(i, lines=True) for i in glob(f'{path}/serps/part*.gz')])
    ret = ret[ret['serp_results'].map(lambda i: len(extract_non_empty_results({'serp_results': i}))) > min_results_on_serp]
    return ret

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
    iteration: str
    search_provider_name: str
    num_results: int
    lang: str

class ArchiveQueryLogQrels(BaseQrels):
    def __init__(self, dlc, lang=None):
        self.qrels = []
        serps = parse_serps(dlc)

        for _, serp in serps.iterrows():
            results = extract_non_empty_results(serp)
            for result in results:
                self.qrels += [ArchiveQueryLogQrel(
                                                   query_id = serp.serp_id, doc_id = result['result_id'],
                                                   relevance = max(0, 10 - result['result_snippet_rank']),
                                                   iteration = 0, search_provider_name= serp.search_provider_name,
                                                   num_results=len(results), lang=serp.serp_query_text_url_language
                                                   )
                              ]

        if lang:
            self.qrels = [i for i in self.qrels if i.lang==lang]
        print(f'Have {len(self.qrels)} qrels.')

    def qrels_iter(self):
        return deepcopy(self.qrels).__iter__()

    def qrels_path(self):
        raise NotImplementedError()

    def qrels_cls(self):
        return ArchiveQueryLogQrel

    def qrels_defs(self):
        raise NotImplementedError()

class ArchiveQueryLogQueries:
    def __init__(self, dlc, lang=None):
        serps = parse_serps(dlc)
        self.queries = []
        
        for _, serp in serps.iterrows():
            num_results = len(extract_non_empty_results(serp))
            if num_results < 1:
                continue
            self.queries += [ArchiveQueryLogQuery(query_id = serp.serp_id, text = serp.serp_query_text_html,
                                                  lang=serp.serp_query_text_url_language,
                                                  search_provider_name= serp.search_provider_name, num_results=num_results
                                                  )
                            ]
        if lang:
            self.queries = [i for i in self.queries if i.lang==lang]

        print(f'Have {len(self.queries)} queries.')

    def queries_iter(self):
        return deepcopy(self.queries).__iter__()

class ArchiveQueryLogDocs(BaseDocs):
    def __init__(self, dlc):
        self.df = parse_serps(dlc)
        self.docs = []

        for _, i in self.df.iterrows():
            for result in extract_non_empty_results(i):
                self.docs += [GenericDoc(doc_id=result['result_id'], text=(result['result_snippet_title'] + ' ' + result['result_snippet_title']).strip())]

        print(f'Have {self.docs_count()} documents.')

    def docs_iter(self):
        return deepcopy(self.docs).__iter__()

    def docs_count(self):
        return len(self.docs)

    def docs_store(self):
        return PickleLz4FullStore(
            path=f'{self._dlc.path(force=False)}.pklz4',
            init_iter_fn=self.docs_iter,
            data_cls=self.docs_cls(),
            lookup_field='doc_id',
            index_fields=['doc_id'],
        )


dataset = Dataset(ArchiveQueryLogDocs('/data/'), ArchiveQueryLogQueries('/data/'), ArchiveQueryLogQrels('/data/'))
ir_datasets.registry.register('archive-query-log', dataset)

assert dataset.has_docs(), "dataset has no documents"
assert dataset.has_queries(), "dataset has no queries"

