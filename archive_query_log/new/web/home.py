from typing import NamedTuple, Type

from elasticsearch_dsl import Document
from elasticsearch_dsl.query import Script, Exists
from expiringdict import ExpiringDict
from flask import render_template

from archive_query_log.new.config import Config
from archive_query_log.new.orm import Archive, Provider, Source, Capture
from archive_query_log.new.utils.time import utc_now


class Statistics(NamedTuple):
    name: str
    description: str
    total: str


class Progress(NamedTuple):
    name: str
    description: str
    total: int
    current: int


_statistics_cache: dict[str, Statistics] = ExpiringDict(
    max_len=100,
    max_age_seconds=60,
)


def _get_statistics(
        config: Config,
        name: str,
        description: str,
        document: Type[Document],
) -> Statistics:
    if name in _statistics_cache:
        return _statistics_cache[name]
    search = document.search(using=config.es.client)
    total = search.extra(track_total_hits=True).execute().hits.total.value
    statistics = Statistics(
        name=name,
        description=description,
        total=total,
    )
    _statistics_cache[name] = statistics
    return statistics


_progress_cache: dict[str, Progress] = ExpiringDict(
    max_len=100,
    max_age_seconds=60,
)


def _get_progress(
        config: Config,
        name: str,
        description: str,
        document: Type[Document],
        processed_timestamp_field: str,
) -> Progress:
    if name in _progress_cache:
        return _progress_cache[name]

    search = document.search(using=config.es.client)
    total = search.extra(track_total_hits=True).execute().hits.total.value
    search_processed = search.filter(
        Exists(field="last_modified") &
        Exists(field=processed_timestamp_field) &
        Script(
            script=f"doc['last_modified'].value.isBefore("
                   f"doc['{processed_timestamp_field}'].value)",
        )
    )
    total_processed = (search_processed.extra(track_total_hits=True).execute()
                       .hits.total.value)

    progress = Progress(
        name=name,
        description=description,
        total=total,
        current=total_processed,
    )
    _progress_cache[name] = progress
    return progress


def home(config: Config) -> str:
    statistics_list: list[Statistics] = []
    statistics_list.append(_get_statistics(
        config=config,
        name="Archives",
        description="Web archiving services that offer CDX "
                    "and Memento APIs.",
        document=Archive,
    ))
    statistics_list.append(_get_statistics(
        config=config,
        name="Providers",
        description="Search providers, i.e., websites that offer "
                    "a search functionality.",
        document=Provider,
    ))
    statistics_list.append(_get_statistics(
        config=config,
        name="Sources",
        description="The cross product of all archives and "
                    "the provider's domains and URL prefixes.",
        document=Source,
    ))
    statistics_list.append(_get_statistics(
        config=config,
        name="Captures",
        description="Captures matching from the archives "
                    "that match domain and URL prefixes.",
        document=Capture,
    ))

    progress_stages: list[Progress] = []
    progress_stages.append(_get_progress(
        config=config,
        name="Archives → Sources",
        description="Build sources for all archives.",
        document=Archive,
        processed_timestamp_field="last_built_sources",
    ))
    progress_stages.append(_get_progress(
        config=config,
        name="Providers → Sources",
        description="Build sources for all search providers.",
        document=Provider,
        processed_timestamp_field="last_built_sources",
    ))
    progress_stages.append(_get_progress(
        config=config,
        name="Sources → Captures",
        description="Fetch CDX captures for all domains and "
                    "prefixes in the sources.",
        document=Source,
        processed_timestamp_field="last_fetched_captures",
    ))

    return render_template(
        "home.html",
        count_stages=statistics_list,
        progress_stages=progress_stages,
        year=utc_now().year,
    )
