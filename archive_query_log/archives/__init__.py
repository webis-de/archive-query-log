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
        no_merge: bool = False,
        auto_merge: bool = False,
) -> None:
    Archive.index().refresh(using=config.es.client)
    last_modified = utc_now()
    existing_archive_search: Search = (
        Archive.search(using=config.es.client)
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

        if cdx_api_url == existing_archive.cdx_api_url and \
                memento_api_url == existing_archive.memento_api_url:
            last_modified = existing_archive.last_modified

        if not auto_merge:
            echo(f"Update archive {archive_id}.")
    else:
        archive_id = str(uuid4())
        if not no_merge and not auto_merge:
            echo(f"Add new archive {archive_id}.")

    archive = Archive(
        meta={"id": archive_id},
        name=name,
        description=description,
        cdx_api_url=cdx_api_url,
        memento_api_url=memento_api_url,
        last_modified=last_modified,
    )
    archive.save(using=config.es.client)
