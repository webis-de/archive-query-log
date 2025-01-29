from uuid import uuid4

from click import echo, prompt
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Term
from elasticsearch_dsl.response import Response

from archive_query_log.config import Config
from archive_query_log.orm import Archive
from archive_query_log.utils.time import utc_now


def add_archive(
        config: Config,
        name: str | None,
        description: str | None,
        cdx_api_url: str,
        memento_api_url: str,
        priority: float | None,
        no_merge: bool = False,
        auto_merge: bool = False,
) -> None:
    if priority is not None and priority <= 0:
        raise ValueError("Priority must be strictly positive.")
    config.es.client.indices.refresh(index=config.es.index_archives)
    last_modified = utc_now()
    should_build_sources = True
    existing_archive_search: Search = (
        Archive.search(using=config.es.client, index=config.es.index_archives)
        .query(
            Term(cdx_api_url=cdx_api_url) |
            Term(memento_api_url=memento_api_url)
        )
    )
    existing_archive_response: Response = existing_archive_search.execute()
    if existing_archive_response.hits.total.value > 0:
        if no_merge:
            return
        existing_archive: Archive = existing_archive_response[0]
        archive_id = existing_archive.id
        if auto_merge:
            should_merge = True
        else:
            echo(f"Archive {archive_id} already exists with "
                 f"conflicting API endpoints.")
            add_to_existing = prompt("Merge with existing archive? [y/N]",
                                     type=str, default="n", show_default=False)
            should_merge = add_to_existing.lower() == "y"
        if not should_merge:
            return

        if name is None:
            name = existing_archive.name
        if description is None:
            description = existing_archive.description
        if priority is None:
            priority = existing_archive.priority

        if cdx_api_url == existing_archive.cdx_api_url and \
                memento_api_url == existing_archive.memento_api_url:
            last_modified = existing_archive.last_modified
            should_build_sources = existing_archive.should_build_sources

        if not auto_merge:
            echo(f"Update archive {archive_id}.")
    else:
        archive_id = str(uuid4())
        if not no_merge and not auto_merge:
            echo(f"Add new archive {archive_id}.")

    archive = Archive(
        id=archive_id,
        last_modified=last_modified,
        name=name,
        description=description,
        cdx_api_url=cdx_api_url,
        memento_api_url=memento_api_url,
        priority=priority,
        should_build_sources=should_build_sources,
    )
    archive.save(using=config.es.client, index=config.es.index_archives)
