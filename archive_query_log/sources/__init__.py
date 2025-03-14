from itertools import chain
from typing import Iterable, Iterator
from uuid import uuid5
from warnings import warn

from click import echo
from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Exists, Term
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_SOURCE
from archive_query_log.orm import Archive, Provider, Source, InnerArchive, InnerProvider
from archive_query_log.utils.es import safe_iter_scan, update_action
from archive_query_log.utils.time import utc_now


def _sources_batch(archive: Archive, provider: Provider, config: Config) -> list[dict]:
    if provider.exclusion_reason is not None:
        warn(
            f"Skipping provider {provider.id} "
            f"because it is excluded: {provider.exclusion_reason}"
        )
        return []

    batch = []
    for domain in provider.domains:
        for url_path_prefix in provider.url_path_prefixes:
            source_id_components = (
                archive.cdx_api_url,
                archive.memento_api_url,
                domain,
                url_path_prefix,
            )
            source_id = str(
                uuid5(
                    NAMESPACE_SOURCE,
                    ":".join(source_id_components),
                )
            )
            source = Source(
                id=source_id,
                last_modified=utc_now(),
                archive=InnerArchive(
                    id=archive.id,
                    cdx_api_url=archive.cdx_api_url,
                    memento_api_url=archive.memento_api_url,
                    priority=archive.priority,
                ),
                provider=InnerProvider(
                    id=provider.id,
                    domain=domain,
                    url_path_prefix=url_path_prefix,
                    priority=provider.priority,
                ),
                should_fetch_captures=True,
            )
            source.meta.index = config.es.index_sources
            batch.append(source.to_dict(include_meta=True))
    return batch


def _iter_sources_batches_changed_archives(
    changed_archives_search: Search,
    all_providers_search: Search,
    config: Config,
) -> Iterator[list[dict]]:
    archive: Archive
    provider: Provider
    changed_archives = changed_archives_search.scan()
    changed_archives = safe_iter_scan(changed_archives)
    for archive in changed_archives:
        all_providers = all_providers_search.scan()
        all_providers = safe_iter_scan(all_providers)
        for provider in all_providers:
            yield _sources_batch(
                archive,
                provider,
                config,
            )
        yield [
            update_action(
                archive,
                should_build_sources=False,
                last_built_sources=utc_now(),
            )
        ]


def _iter_sources_batches_changed_providers(
    changed_providers_search: Search,
    all_archives_search: Search,
    config: Config,
) -> Iterator[list[dict]]:
    archive: Archive
    provider: Provider
    changed_providers = changed_providers_search.scan()
    changed_providers = safe_iter_scan(changed_providers)
    for provider in changed_providers:
        all_archives = all_archives_search.scan()
        all_archives = safe_iter_scan(all_archives)
        for archive in all_archives:
            yield _sources_batch(
                archive,
                provider,
                config,
            )
        yield [
            update_action(
                provider,
                should_build_sources=False,
                last_built_sources=utc_now(),
            )
        ]


def _build_archive_sources(config: Config) -> None:
    config.es.client.indices.refresh(index=config.es.index_archives)
    config.es.client.indices.refresh(index=config.es.index_providers)
    changed_archives_search = (
        Archive.search(using=config.es.client, index=config.es.index_archives)
        .filter(~Term(should_build_sources=False))
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_archives = changed_archives_search.count()
    all_providers_search = Provider.search(
        using=config.es.client, index=config.es.index_providers
    ).filter(~Exists(field="exclusion_reason"))
    num_all_providers = all_providers_search.count()
    num_batches_archives = (
        num_changed_archives * num_all_providers
    ) + num_changed_archives
    if num_batches_archives > 0:
        echo(f"Building sources for {num_changed_archives} " f"new/changed archives.")
        action_batches_archives: Iterable[list[dict]] = (
            _iter_sources_batches_changed_archives(
                changed_archives_search=changed_archives_search,
                all_providers_search=all_providers_search,
                config=config,
            )
        )
        # noinspection PyTypeChecker
        action_batches_archives = tqdm(
            action_batches_archives,
            total=num_batches_archives,
            desc="Build sources",
            unit="batch",
        )
        actions_archives = chain.from_iterable(action_batches_archives)
        config.es.bulk(actions_archives)
    else:
        echo("No new/changed archives.")


def _build_provider_sources(config: Config) -> None:
    config.es.client.indices.refresh(index=config.es.index_archives)
    config.es.client.indices.refresh(index=config.es.index_providers)
    changed_providers_search = (
        Provider.search(using=config.es.client, index=config.es.index_providers)
        .filter(~Term(should_build_sources=False))
        .query(FunctionScore(functions=[RandomScore()]))
    )
    num_changed_providers = changed_providers_search.count()
    all_archives_search = Archive.search(
        using=config.es.client, index=config.es.index_archives
    )
    num_all_archives = all_archives_search.count()
    num_batches_providers = (
        num_changed_providers * num_all_archives
    ) + num_changed_providers
    if num_batches_providers > 0:
        echo(f"Building sources for {num_changed_providers} " f"new/changed providers.")
        action_batches_providers: Iterable[list[dict]] = (
            _iter_sources_batches_changed_providers(
                changed_providers_search=changed_providers_search,
                all_archives_search=all_archives_search,
                config=config,
            )
        )
        # noinspection PyTypeChecker
        action_batches_providers = tqdm(
            action_batches_providers,
            total=num_batches_providers,
            desc="Build sources",
            unit="batch",
        )
        actions_providers = chain.from_iterable(action_batches_providers)
        config.es.bulk(actions_providers)
    else:
        echo("No new/changed providers.")


def build_sources(
    config: Config,
    skip_archives: bool,
    skip_providers: bool,
) -> None:
    if not skip_archives:
        _build_archive_sources(config)
    if not skip_providers:
        _build_provider_sources(config)
