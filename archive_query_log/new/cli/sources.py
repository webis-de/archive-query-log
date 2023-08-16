from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator, Any
from uuid import uuid5

from click import group, echo, option
from elasticsearch.helpers import parallel_bulk
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Script, Bool
from tqdm.auto import tqdm

from archive_query_log.new.cli.util import pass_config
from archive_query_log.new.config import Config
from archive_query_log.new.namespaces import NAMESPACE_SOURCE
from archive_query_log.new.orm import (
    Archive, Provider, Source, InnerArchive, InnerProvider)
from archive_query_log.new.utils.time import utc_now


@group()
def sources():
    pass


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
                ),
                last_modified=utc_now(),
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
@pass_config
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

    start_time = utc_now()

    if not skip_archives:
        changed_archives_search: Search = (
            Archive.search(using=config.es)
            .query(FunctionScore(
                query=Bool(
                    filter=Script(
                        script="doc['last_modified'].value.isAfter("
                               "doc['last_built_sources'].value)",
                    )
                ),
                functions=[RandomScore(
                    seed=int(utc_now().timestamp()),
                    field="_seq_no",
                )]
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
                 f"new/changed archives.")
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
            echo(f"No new/changed archives.")

    if not skip_providers:
        changed_providers_search: Search = (
            Provider.search(using=config.es)
            .query(FunctionScore(
                query=Bool(
                    filter=Script(
                        script="doc['last_modified'].value.isAfter("
                               "doc['last_built_sources'].value)",
                    )
                ),
                functions=[RandomScore(
                    seed=int(utc_now().timestamp()),
                    field="_seq_no",
                )]
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
                f"new/changed providers.")
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
            echo(f"No new/changed providers.")
    Archive.index().refresh(using=config.es)
    Provider.index().refresh(using=config.es)
    Source.index().refresh(using=config.es)
