from urllib.parse import urljoin
from uuid import uuid4

from click import group, option, echo, IntRange, prompt
from elasticsearch_dsl import Search
from elasticsearch_dsl.query import Term
from elasticsearch_dsl.response import Response
from tqdm.auto import tqdm

from archive_query_log.cli.util import pass_config
from archive_query_log.config import Config
from archive_query_log.orm import Archive
from archive_query_log.utils.time import utc_now


@group()
def archives():
    pass


def _add_archive(
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
    archive.save(using=config.es.client, refresh=True)


@archives.command()
@option("-n", "--name", type=str, required=True,
        prompt="Name")
@option("-d", "--description", type=str)
@option("-c", "--cdx-api-url", type=str, required=True,
        prompt="CDX API URL", metavar="URL")
@option("-m", "--memento-api-url", type=str, required=True,
        prompt="Memento API URL", metavar="URL")
@pass_config
def add(
        config: Config,
        name: str,
        description: str | None,
        cdx_api_url: str,
        memento_api_url: str,
) -> None:
    Archive.init(using=config.es.client)
    _add_archive(
        config=config,
        name=name,
        description=description,
        cdx_api_url=cdx_api_url,
        memento_api_url=memento_api_url,
    )


@archives.group("import")
def import_():
    pass


ARCHIVE_IT_METADATA_FIELDS = [
    "Title",
    "Description",
    "Subject",
    "Coverage",
    "Language",
    "Collector",
    "Creator",
    "Publisher",
    "Date",
    "Identifier",
    "Rights",
]


@import_.command()
@option("--api-url", type=str, required=True,
        default="https://partner.archive-it.org", metavar="URL")
@option("--wayback-url", type=str, required=True,
        default="https://wayback.archive-it.org", metavar="URL")
@option("--page-size", type=IntRange(min=1), required=True,
        default=100)
@option("--no-merge", is_flag=True, default=False, type=bool)
@option("--auto-merge", is_flag=True, default=False, type=bool)
@pass_config
def archive_it(
        config: Config,
        api_url: str,
        wayback_url: str,
        page_size: int,
        no_merge: bool,
        auto_merge: bool,
) -> None:
    Archive.init(using=config.es.client)

    echo("Load Archive-It collections.")
    collections_api_url = urljoin(api_url, "/api/collection")
    response = config.http.session.get(
        collections_api_url,
        params=[
            ("limit", 0),
            ("format", "json"),
        ],
    )
    num_collections = int(response.headers["Total-Row-Count"])
    echo(f"Found {num_collections} collections on Archive-It.")

    # noinspection PyTypeChecker
    progress = tqdm(total=num_collections, desc="Import archives",
                    unit="archives", disable=not auto_merge and not no_merge)
    offset_range = range(0, num_collections, page_size)
    for offset in offset_range:
        response = config.http.session.get(
            collections_api_url,
            params=[
                ("limit", page_size),
                ("offset", offset),
                ("format", "json"),
            ],
        )
        response_list = response.json()
        for item in response_list:
            name = f"Archive-It {item['name']}"
            archive_it_id = int(item["id"])

            description_parts = []
            metadata = item["metadata"]
            for metadata_field in ARCHIVE_IT_METADATA_FIELDS:
                if metadata_field in metadata:
                    for title in metadata[metadata_field]:
                        description_parts.append(
                            f"{metadata_field}: {title['value']}")
            description_parts.append(f"Archive-It ID: {archive_it_id}")
            description = "\n".join(description_parts)
            cdx_api_url = urljoin(wayback_url, f"{archive_it_id}/timemap/cdx")
            memento_api_url = urljoin(wayback_url, f"{archive_it_id}")
            _add_archive(
                config=config,
                name=name,
                description=description,
                cdx_api_url=cdx_api_url,
                memento_api_url=memento_api_url,
                no_merge=no_merge,
                auto_merge=auto_merge,
            )
            progress.update(1)
