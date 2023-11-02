from datetime import datetime
from itertools import chain
from typing import Iterable, Iterator, Any
from uuid import uuid5
from warnings import warn

from click import group, echo, option
from elasticsearch import ConnectionTimeout
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Script, Exists
from tqdm.auto import tqdm

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_SOURCE
from archive_query_log.orm import (
    Archive, Provider, Source, InnerArchive, InnerProvider)
from archive_query_log.utils.es import safe_iter_scan
from archive_query_log.utils.time import utc_now


@group()
def sources():
    pass


def _sources_batch(archive: Archive, provider: Provider) -> list[dict]:
    if provider.exclusion_reason is not None:
        warn(
            f"Skipping provider {provider.id} "
            f"because it is excluded: {provider.exclusion_reason}"
        )
        return []

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
                    id=archive.id,
                    cdx_api_url=archive.cdx_api_url,
                    memento_api_url=archive.memento_api_url,
                ),
                provider=InnerProvider(
                    id=provider.id,
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
    changed_archives = (changed_archives_search.params(preserve_order=True)
                        .scan())
    changed_archives = safe_iter_scan(changed_archives)
    all_providers = all_providers_search.params(preserve_order=True).scan()
    all_providers = safe_iter_scan(all_providers)
    for archive in changed_archives:
        for provider in all_providers:
            yield _sources_batch(
                archive,
                provider,
            )
        archive.update(
            using=config.es.client,
            retry_on_conflict=3,
            last_built_sources=start_time,
            refresh=True,
        )


def _iter_sources_batches_changed_providers(
        config: Config,
        changed_providers_search: Search,
        all_archives_search: Search,
        start_time: datetime,
) -> Iterator[list[dict]]:
    archive: Archive
    provider: Provider
    changed_providers = (changed_providers_search.params(preserve_order=True)
                         .scan())
    changed_providers = safe_iter_scan(changed_providers)
    all_archives = all_archives_search.params(preserve_order=True).scan()
    all_archives = safe_iter_scan(all_archives)
    for provider in changed_providers:
        for archive in all_archives:
            yield _sources_batch(
                archive,
                provider,
            )
        provider.update(
            using=config.es.client,
            retry_on_conflict=3,
            last_built_sources=start_time,
            refresh=True,
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
    Source.init(using=config.es.client)

    start_time = utc_now()

    if not skip_archives:
        changed_archives_search = (
            Archive.search(using=config.es.client)
            .filter(
                ~Exists(field="last_modified") |
                ~Exists(field="last_built_sources") |
                Script(
                    script="!doc['last_modified'].isEmpty() && "
                           "!doc['last_built_sources'].isEmpty() && "
                           "!doc['last_modified'].value.isBefore("
                           "doc['last_built_sources'].value)",
                )
            )
            .query(FunctionScore(functions=[RandomScore()]))
        )
        num_changed_archives_search = (
            changed_archives_search.extra(track_total_hits=True))
        num_changed_archives = (
            num_changed_archives_search.execute().hits.total.value)
        all_providers_search = (
            Provider.search(using=config.es.client)
            .filter(~Exists(field="exclusion_reason")))
        num_all_providers_search = (
            all_providers_search.extra(track_total_hits=True))
        num_all_providers = (
            num_all_providers_search.execute().hits.total.value)
        num_batches_archives = num_changed_archives * num_all_providers
        if num_batches_archives > 0:
            echo(f"Building sources for {num_changed_archives} "
                 f"new/changed archives.")
            action_batches_archives: Iterable[list[dict]] = (
                _iter_sources_batches_changed_archives(
                    config=config,
                    changed_archives_search=changed_archives_search,
                    all_providers_search=all_providers_search,
                    start_time=start_time,
                ))
            # noinspection PyTypeChecker
            action_batches_archives = tqdm(
                action_batches_archives,
                total=num_batches_archives,
                desc="Build sources",
                unit="batch",
            )
            actions_archives = chain.from_iterable(action_batches_archives)
            try:
                responses_archives: Iterable[
                    tuple[bool, Any]] = config.es.streaming_bulk(
                    actions=actions_archives,
                )
            except ConnectionTimeout:
                warn(RuntimeWarning(
                    "Connection timeout while indexing captures."))
                return

            for success, info in responses_archives:
                if not success:
                    raise RuntimeError(f"Indexing error: {info}")
            Source.index().refresh(using=config.es.client)
        else:
            echo("No new/changed archives.")

    if not skip_providers:
        changed_providers_search = (
            Provider.search(using=config.es.client)
            .filter(
                ~Exists(field="exclusion_reason") &
                (
                        ~Exists(field="last_modified") |
                        ~Exists(field="last_built_sources") |
                        Script(
                            script="!doc['last_modified'].isEmpty() && "
                                   "!doc['last_built_sources'].isEmpty() && "
                                   "!doc['last_modified'].value.isBefore("
                                   "doc['last_built_sources'].value)",
                        )
                )
            )
            .query(FunctionScore(functions=[RandomScore()]))
        )
        num_changed_providers_search = (
            changed_providers_search.extra(track_total_hits=True))
        num_changed_providers = (
            num_changed_providers_search.execute().hits.total.value)
        all_archives_search = Archive.search(using=config.es.client)
        num_all_archives_search = (
            all_archives_search.extra(track_total_hits=True))
        # pylint: disable=no-member
        num_all_archives = (
            num_all_archives_search.execute().hits.total.value)
        num_batches_providers = num_changed_providers * num_all_archives
        if num_batches_providers > 0:
            echo(
                f"Building sources for {num_changed_providers} "
                f"new/changed providers.")
            action_batches_providers: Iterable[list[dict]] = (
                _iter_sources_batches_changed_providers(
                    config=config,
                    changed_providers_search=changed_providers_search,
                    all_archives_search=all_archives_search,
                    start_time=start_time,
                ))
            # noinspection PyTypeChecker
            action_batches_providers = tqdm(
                action_batches_providers,
                total=num_batches_providers,
                desc="Build sources",
                unit="batch",
            )
            actions_providers = chain.from_iterable(action_batches_providers)
            try:
                responses: Iterable[tuple[bool, Any]] = (
                    config.es.streaming_bulk(
                        actions=actions_providers,
                        initial_backoff=2,
                        max_backoff=600,
                    ))
            except ConnectionTimeout:
                warn(RuntimeWarning(
                    "Connection timeout while indexing captures."))
                return
            for success, info in responses:
                if not success:
                    raise RuntimeError(f"Indexing error: {info}")
            Source.index().refresh(using=config.es.client)
        else:
            echo("No new/changed providers.")
