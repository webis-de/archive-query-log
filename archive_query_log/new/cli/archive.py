from datetime import datetime
from urllib.parse import urljoin
from uuid import uuid5

from click import group, argument, option, echo, IntRange
from elasticsearch.helpers import parallel_bulk
from tqdm.auto import trange, tqdm

from archive_query_log.new.config import CONFIG
from archive_query_log.new.http import session
from archive_query_log.new.namespaces import NAMESPACE_ARCHIVE
from archive_query_log.new.utils.es import create_index


@group()
def archive():
    pass


@archive.command()
@argument("name", type=str)
@option("-d", "--description", type=str)
@option("-c", "--cdx-api-url", type=str, required=True,
        prompt="CDX API URL", metavar="URL")
@option("-m", "--memento-api-url", type=str, required=True,
        prompt="Memento API URL", metavar="URL")
def add(
        name: str,
        description: str | None,
        cdx_api_url: str,
        memento_api_url: str,
) -> None:
    create_index(CONFIG.es_index_archives)
    archive_id = str(uuid5(NAMESPACE_ARCHIVE, name))
    document = {
        "id": archive_id,
        "name": name,
        "description": description,
        "cdx_api_url": cdx_api_url,
        "memento_api_url": memento_api_url,
        "last_modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    echo(f"Add archive {archive_id}.")
    CONFIG.es.index(
        index=CONFIG.es_index_archives.name,
        id=archive_id,
        document=document,
    )
    echo(f"Refresh index {CONFIG.es_index_archives.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_archives.name)
    echo("Done.")


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


@archive.command()
@option("--api-url", type=str, required=True,
        default="https://partner.archive-it.org", metavar="URL")
@option("--wayback-url", type=str, required=True,
        default="https://wayback.archive-it.org", metavar="URL")
@option("--page-size", type=IntRange(min=1), required=True,
        default=100)
def add_archive_it_collections(api_url: str, wayback_url: str,
                               page_size: int) -> None:
    echo("Load Archive-It collections.")
    collections_api_url = urljoin(api_url, "/api/collection")
    response = session.get(collections_api_url,
                           params={"limit": 0, "format": "json"})
    num_collections = int(response.headers["Total-Row-Count"])
    echo(f"Found {num_collections} collections on Archive-It.")

    documents = []
    offset_range = trange(0, num_collections, page_size,
                          desc="Load collections")
    # noinspection PyTypeChecker
    for offset in offset_range:
        response = session.get(collections_api_url,
                               params={"limit": page_size, "offset": offset,
                                       "format": "json"})
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

            archive_id = str(uuid5(NAMESPACE_ARCHIVE, name))
            cdx_api_url = urljoin(wayback_url, f"{archive_it_id}/timemap/cdx")
            memento_api_url = urljoin(wayback_url, f"{archive_it_id}")

            document = {
                "id": archive_id,
                "name": name,
                "description": description,
                "cdx_api_url": cdx_api_url,
                "memento_api_url": memento_api_url,
                "last_modified": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            documents.append(document)
    echo(f"Found {len(documents)} archives (Archive-It collections).")

    create_index(CONFIG.es_index_archives)
    operations = (
        {
            "_op_type": "create",
            "_index": CONFIG.es_index_archives.name,
            "_id": document["id"],
            **document,
        }
        for document in documents
    )
    has_errors = False
    # noinspection PyTypeChecker
    for success, info in tqdm(
            parallel_bulk(
                CONFIG.es,
                operations,
                ignore_status=[409],
            ),
            desc="Adding archives",
            total=len(documents),
            unit="capture",
    ):
        if not success:
            if info["create"]["status"] != 409:
                echo("Indexing error:", info, err=True)
                has_errors = True
    if has_errors:
        raise RuntimeError("Indexing errors occurred.")

    echo(f"Refresh index {CONFIG.es_index_archives.name}.")
    CONFIG.es.indices.refresh(index=CONFIG.es_index_archives.name)

    echo("Done.")
