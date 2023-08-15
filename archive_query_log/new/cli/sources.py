from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator, Any
from uuid import uuid5

from click import group, echo, Context, pass_context, pass_obj, option
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import Range, Exists, FunctionScore
from elasticsearch_dsl.response import Response
from tqdm.auto import tqdm

from archive_query_log.new.config import Config
from archive_query_log.new.namespaces import NAMESPACE_SOURCE
from archive_query_log.new.orm import (
    Archive, Provider, Source, InnerArchive, InnerProvider)
from archive_query_log.new.utils.time import EPOCH, current_time


@group()
@pass_obj
@pass_context
def sources(context: Context, config: Config):
    context.obj = config


def _sources_batch(archive: Archive, provider: Provider) -> list[dict]:
    batch = []
    for domain in provider.domains:
        for url_path_prefix in provider.url_path_prefixes:
            filter_id_components = (
                archive.cdx_api_url,
                archive.memento_api_url,
                domain,
                url_path_prefix,
            )
            filter_id = str(uuid5(
                NAMESPACE_SOURCE,
                ":".join(filter_id_components),
            ))
            source = Source(
                meta={"id": filter_id},
                archive=InnerArchive(
                    id=archive.meta.id,
                    cdx_api_url=archive.cdx_api_url,
                    memento_api_url=archive.memento_api_url,
                ),
                provider=InnerProvider(
                    id=provider.meta.id,
                    domain=domain,
                    url_path_prefix=url_path_prefix,
                )
            )
            batch.append(source.to_dict(include_meta=True))
    return batch


def _iter_sources_batches_changed_archives(
        config: Config,
        changed_archives_search: Search,
        all_providers_search: Search,
        start_time: datetime,
) -> Iterator[list[dict]]:
    archive: Archive
    provider: Provider
    for archive in changed_archives_search.scan():
        for provider in all_providers_search.scan():
            yield _sources_batch(
                archive,
                provider,
            )
        archive.update(
            using=config.es,
            last_built_sources=start_time,
        )


def _iter_sources_batches_changed_providers(
        config: Config,
        changed_providers_search: Search,
        all_archives_search: Search,
        start_time: datetime,
) -> Iterator[list[dict]]:
    archive: Archive
    provider: Provider
    for provider in changed_providers_search.scan():
        for archive in all_archives_search.scan():
            yield _sources_batch(
                archive,
                provider,
            )
        provider.update(
            using=config.es,
            last_built_sources=start_time,
        )


@sources.command()
@option("--skip-archives", is_flag=True)
@option("--skip-providers", is_flag=True)
@pass_obj
def build(
        config: Config,
        skip_archives: bool,
        skip_providers: bool,
) -> None:
    Archive.init(using=config.es)
    Archive.index().refresh(using=config.es)
    Provider.init(using=config.es)
    Provider.index().refresh(using=config.es)
    Source.init(using=config.es)

    start_time = current_time()

    if not skip_archives:
        last_archive_response: Response = (
            Archive.search(using=config.es)
            .query(Exists(field="last_built_sources"))
            .sort("-last_built_sources")
            .execute()
        )
        if last_archive_response.hits.total.value == 0:
            last_archive_time = EPOCH
        else:
            last_archive_time = last_archive_response[0].last_built_sources
        changed_archives_search: Search = (
            Archive.search(using=config.es)
            .query(FunctionScore(
                query=~Range(last_built_sources={"lte": last_archive_time}),
                functions=[RandomScore()]
            ))
        )
        num_changed_archives = (
            changed_archives_search.extra(track_total_hits=True)
            .execute().hits.total.value)
        all_providers_search: Search = Provider.search(using=config.es)
        num_all_providers = (all_providers_search.extra(track_total_hits=True)
                             .execute().hits.total.value)
        num_batches = num_changed_archives * num_all_providers
        if num_batches > 0:
            echo(f"Building sources for {num_changed_archives} "
                 f"new/changed archives "
                 f"since {last_archive_time.astimezone().strftime('%c')}.")
            action_batches: Iterator[
                list[dict]] = _iter_sources_batches_changed_archives(
                config=config,
                changed_archives_search=changed_archives_search,
                all_providers_search=all_providers_search,
                start_time=start_time,
            )
            # noinspection PyTypeChecker
            action_batches = tqdm(action_batches, total=num_batches,
                                  desc="Build sources", unit="batch")
            actions = chain.from_iterable(action_batches)
            responses: Iterable[tuple[bool, Any]] = parallel_bulk(
                client=config.es,
                actions=actions,
            )
            for success, info in responses:
                if not success:
                    raise RuntimeError(f"Indexing error: {info}")
        else:
            echo(f"No new/changed archives "
                 f"since {last_archive_time.astimezone().strftime('%c')}.")

    if not skip_providers:
        last_provider_response: Response = (
            Provider.search(using=config.es)
            .query(Exists(field="last_built_sources"))
            .sort("-last_built_sources")
            .execute()
        )
        if last_provider_response.hits.total.value == 0:
            last_provider_time = EPOCH
        else:
            last_provider_time = last_provider_response[0].last_built_sources
        changed_providers_search: Search = (
            Provider.search(using=config.es)
            .query(FunctionScore(
                query=~Range(last_built_sources={"lte": last_provider_time}),
                functions=[RandomScore()]
            ))
        )
        num_changed_providers = (
            changed_providers_search.extra(track_total_hits=True)
            .execute().hits.total.value)
        all_archives_search: Search = Archive.search(using=config.es)
        num_all_archives = (all_archives_search.extra(track_total_hits=True)
                            .execute().hits.total.value)
        num_batches = num_changed_providers * num_all_archives
        if num_batches > 0:
            echo(
                f"Building sources for {num_changed_providers} "
                f"new/changed providers "
                f"since {last_provider_time.astimezone().strftime('%c')}.")
            action_batches: Iterator[
                list[dict]] = _iter_sources_batches_changed_providers(
                config=config,
                changed_providers_search=changed_providers_search,
                all_archives_search=all_archives_search,
                start_time=start_time,
            )
            # noinspection PyTypeChecker
            action_batches = tqdm(action_batches, total=num_batches,
                                  desc="Build sources", unit="batch")
            actions = chain.from_iterable(action_batches)
            responses: Iterable[tuple[bool, Any]] = parallel_bulk(
                client=config.es,
                actions=actions,
            )
            for success, info in responses:
                if not success:
                    raise RuntimeError(f"Indexing error: {info}")
        else:
            echo(f"No new/changed providers "
                 f"since {last_provider_time.astimezone().strftime('%c')}.")
    Archive.index().refresh(using=config.es)
    Provider.index().refresh(using=config.es)
    Source.index().refresh(using=config.es)
