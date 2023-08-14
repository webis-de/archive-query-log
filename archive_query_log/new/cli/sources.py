from datetime import datetime
from typing import Iterable, Callable
from uuid import uuid5

from click import group, echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Range, Exists
from elasticsearch_dsl.response import Response
from tqdm.auto import tqdm

from archive_query_log.new.namespaces import NAMESPACE_SOURCE
from archive_query_log.new.orm import (
    Archive, Provider, Source, SourceArchive, SourceProvider)
from archive_query_log.new.utils.time import EPOCH, current_time


@group()
def sources():
    pass


def _save_sources_inner(
        archive: Archive,
        provider: Provider,
        progress: tqdm,
) -> None:
    for domain in provider.domains:
        for url_path_prefix in provider.url_path_prefixes:
            filter_components = (
                archive.cdx_api_url,
                archive.memento_api_url,
                domain,
                url_path_prefix,
            )
            filter_id = str(uuid5(
                NAMESPACE_SOURCE,
                ":".join(filter_components),
            ))
            source = Source(
                meta={"id": filter_id},
                archive=SourceArchive(
                    id=archive.meta.id,
                    cdx_api_url=archive.cdx_api_url,
                    memento_api_url=archive.memento_api_url,
                ),
                provider=SourceProvider(
                    id=provider.meta.id,
                    domain=domain,
                    url_path_prefix=url_path_prefix,
                )
            )
            source.save()

    progress.update(1)


def _save_sources(
        archives: Callable[[], Iterable[Archive]],
        num_archives: int,
        providers: Callable[[], Iterable[Provider]],
        num_providers: int,
        start_time: datetime,
        progress: tqdm,
) -> None:
    if num_archives >= num_providers:
        for archive in archives():
            for provider in providers():
                _save_sources_inner(
                    archive,
                    provider,
                    progress,
                )
                provider.update(last_built_sources=start_time)
            archive.update(last_built_sources=start_time)
    else:
        for provider in providers():
            for archive in archives():
                _save_sources_inner(
                    archive,
                    provider,
                    progress,
                )
                archive.update(last_built_sources=start_time)
            provider.update(last_built_sources=start_time)


@sources.command()
def build() -> None:
    Archive.init()
    Archive().index.refresh()
    Provider.init()
    Provider().index.refresh()
    Source.init()

    start_time = current_time()

    last_archive_search: Search = (
        Archive.search()
        .query(Exists(field="last_built_sources"))
        .sort("-last_built_sources")
    )
    last_archive_response: Response = last_archive_search.execute()
    if last_archive_response.hits.total.value == 0:
        last_archive_time = EPOCH
    else:
        last_archive_time = (
            last_archive_response[0].last_built_sources)

    last_provider_search: Search = (
        Provider.search()
        .query(Exists(field="last_built_sources"))
        .sort("-last_built_sources")
    )
    last_provider_response: Response = last_provider_search.execute()
    if last_provider_response.hits.total.value == 0:
        last_provider_time = EPOCH
    else:
        last_provider_time = (
            last_provider_response[0].last_built_sources)

    echo(f"Generating sources for archives since {last_archive_time} "
         f"and providers since {last_provider_time}.")

    archives_search: Search = Archive.search()
    num_archives = (
        archives_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    new_archives_search: Search = (
        archives_search
        .query(
            ~Exists(field="last_built_sources") |
            Range(last_built_filters={"gt": last_archive_time})
        )
    )
    num_new_archives = (
        new_archives_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    providers_search: Search = Provider.search()
    num_providers = (
        providers_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    new_providers_search: Search = (
        Provider.search()
        .query(
            ~Exists(field="last_built_filters") |
            Range(last_built_filters={"gt": last_provider_time})
        )
    )
    num_new_providers = (
        new_providers_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    if last_provider_time == EPOCH and last_archive_time == EPOCH:
        num_items = num_archives * num_providers
    else:
        num_items = (num_new_archives * num_providers +
                     num_archives * num_new_providers)
    progress = tqdm(total=num_items, desc="Build filters", unit="archive")

    _save_sources(
        archives=new_archives_search.scan,
        num_archives=num_new_archives,
        providers=providers_search.scan,
        num_providers=num_providers,
        start_time=start_time,
        progress=progress,
    )
    Source().index.refresh()


