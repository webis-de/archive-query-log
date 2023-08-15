from datetime import datetime
from typing import Iterable, Callable, Iterator, Any
from uuid import uuid5

from click import group, echo, Context, pass_context, pass_obj
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Range, Exists, FunctionScore
from elasticsearch_dsl.response import Response
from tqdm.auto import tqdm

from archive_query_log.new.config import Config
from archive_query_log.new.namespaces import NAMESPACE_SOURCE
from archive_query_log.new.orm import (
    Archive, Provider, Source, SourceArchive, SourceProvider)
from archive_query_log.new.utils.time import EPOCH, current_time


@group()
@pass_obj
@pass_context
def sources(context: Context, config: Config):
    context.obj = config


def _iter_sources_inner(
        archive: Archive,
        provider: Provider,
) -> Iterator[dict]:
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
            yield source.to_dict(include_meta=True)


def _iter_sources(
        config: Config,
        archives: Callable[[], Iterable[Archive]],
        num_archives: int,
        providers: Callable[[], Iterable[Provider]],
        num_providers: int,
        start_time: datetime,
) -> Iterator[dict]:
    if num_archives >= num_providers:
        for archive in archives():
            for provider in providers():
                yield from _iter_sources_inner(
                    archive,
                    provider,
                )
                provider.update(
                    using=config.es,
                    last_built_sources=start_time,
                )
            archive.update(
                using=config.es,
                last_built_sources=start_time,
            )
    else:
        for provider in providers():
            for archive in archives():
                yield from _iter_sources_inner(
                    archive,
                    provider,
                )
                archive.update(
                    using=config.es,
                    last_built_sources=start_time,
                )
            provider.update(
                using=config.es,
                last_built_sources=start_time,
            )


@sources.command()
@pass_obj
def build(config: Config) -> None:
    Archive.init(using=config.es)
    Archive.index().refresh(using=config.es)
    Provider.init(using=config.es)
    Provider.index().refresh(using=config.es)
    Source.init(using=config.es)

    start_time = current_time()

    last_archive_search: Search = (
        Archive.search(using=config.es)
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
        Provider.search(using=config.es)
        .query(Exists(field="last_built_sources"))
        .sort("-last_built_sources")
    )
    last_provider_response: Response = last_provider_search.execute()
    if last_provider_response.hits.total.value == 0:
        last_provider_time = EPOCH
    else:
        last_provider_time = (
            last_provider_response[0].last_built_sources)

    echo(f"Generating sources for archives "
         f"since {last_archive_time.astimezone().strftime('%c')} "
         f"and providers "
         f"since {last_provider_time.astimezone().strftime('%c')}.")

    archives_search: Search = Archive.search(using=config.es)
    num_archives = (
        archives_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    new_archives_search: Search = (
        archives_search
        .query(
            FunctionScore(
                query=(
                        ~Exists(field="last_built_sources") |
                        Range(last_built_filters={"gt": last_archive_time})
                ),
                functions=[RandomScore()]
            )
        )
    )
    num_new_archives = (
        new_archives_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    providers_search: Search = Provider.search(using=config.es)
    num_providers = (
        providers_search.extra(track_total_hits=True).execute()
        .hits.total.value
    )
    new_providers_search: Search = (
        Provider.search()
        .query(
            FunctionScore(
                query=(
                        ~Exists(field="last_built_filters") |
                        Range(last_built_filters={"gt": last_provider_time})
                ),
                functions=[RandomScore()]
            )
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

    actions = _iter_sources(
        config=config,
        archives=new_archives_search.scan,
        num_archives=num_new_archives,
        providers=new_providers_search.scan,
        num_providers=num_providers,
        start_time=start_time,
    )

    responses: Iterable[tuple[bool, Any]] = parallel_bulk(
        client=config.es,
        actions=actions,
        ignore_status=[409],
    )
    # noinspection PyTypeChecker
    responses = tqdm(responses, total=num_items, desc="Build sources",
                     unit="source")

    for success, info in responses:
        if not success:
            raise RuntimeError(f"Indexing error: {info}")

    Source.index().refresh(using=config.es)
