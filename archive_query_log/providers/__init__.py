from uuid import uuid4

from click import echo, prompt
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Terms
from elasticsearch_dsl.response import Response

from archive_query_log.config import Config
from archive_query_log.orm import Provider
from archive_query_log.utils.time import utc_now


def add_provider(
    config: Config,
    name: str | None,
    description: str | None,
    notes: str | None,
    exclusion_reason: str | None,
    domains: set[str],
    url_path_prefixes: set[str],
    priority: float | None,
    no_merge: bool = False,
    auto_merge: bool = False,
) -> None:
    if priority is not None and priority <= 0:
        raise ValueError("Priority must be strictly positive.")
    config.es.client.indices.refresh(index=config.es.index_providers)
    last_modified = utc_now()
    should_build_sources = True
    existing_provider_search: Search = Provider.search(
        using=config.es.client, index=config.es.index_providers
    ).query(Terms(domains=list(domains)))
    existing_provider_response: Response = existing_provider_search.execute()
    if existing_provider_response.hits.total.value > 0:
        if no_merge:
            return
        existing_provider: Provider = existing_provider_response[0]
        existing_domains = set(existing_provider.domains)
        existing_url_path_prefixes = set(existing_provider.url_path_prefixes)
        provider_id = existing_provider.id
        if auto_merge:
            should_merge = True
        else:
            intersecting_domains = existing_domains & domains
            first_intersecting_domains = sorted(intersecting_domains)[:5]
            intersecting_domains_text = ", ".join(first_intersecting_domains)
            num_more_intersecting_domains = len(intersecting_domains) - len(
                first_intersecting_domains
            )
            if num_more_intersecting_domains > 0:
                intersecting_domains_text += f" (+{num_more_intersecting_domains} more)"
            echo(
                f"Provider {provider_id} already exists with "
                f"conflicting domains: {intersecting_domains_text}"
            )
            add_to_existing = prompt(
                "Merge with existing provider? " "[y/N]",
                type=str,
                default="n",
                show_default=False,
            )
            should_merge = add_to_existing.lower() == "y"
        if not should_merge:
            return

        if name is None:
            name = existing_provider.name
        if description is None:
            description = existing_provider.description
        if notes is None:
            notes = existing_provider.notes
        if exclusion_reason is None:
            exclusion_reason = existing_provider.exclusion_reason
        if priority is None:
            priority = existing_provider.priority

        if (
            domains | existing_domains == existing_domains
            and url_path_prefixes | existing_url_path_prefixes
            == existing_url_path_prefixes
        ):
            last_modified = existing_provider.last_modified
            should_build_sources = existing_provider.should_build_sources

        domains = domains | existing_domains
        url_path_prefixes = url_path_prefixes | existing_url_path_prefixes

        if not auto_merge:
            echo(f"Update provider {provider_id}.")
    else:
        provider_id = str(uuid4())
        if not no_merge and not auto_merge:
            echo(f"Add new provider {provider_id}.")

    provider = Provider(
        id=provider_id,
        last_modified=last_modified,
        name=name,
        description=description,
        notes=notes,
        exclusion_reason=exclusion_reason,
        domains=list(domains),
        url_path_prefixes=list(url_path_prefixes),
        priority=priority,
        should_build_sources=should_build_sources,
    )
    provider.save(using=config.es.client, index=config.es.index_providers)
