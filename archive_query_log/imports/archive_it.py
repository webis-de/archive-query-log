from urllib.parse import urljoin

from click import echo
from tqdm.auto import tqdm

from archive_query_log.archives import add_archive
from archive_query_log.config import Config

_ARCHIVE_IT_METADATA_FIELDS = [
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

DEFAULT_ARCHIVE_IT_API_URL: str = "https://partner.archive-it.org"
DEFAULT_ARCHIVE_IT_WAYBACK_URL: str = "https://wayback.archive-it.org/"
DEFAULT_ARCHIVE_IT_PAGE_SIZE: int = 100


def import_archives(
        config: Config,
        api_url: str = DEFAULT_ARCHIVE_IT_API_URL,
        wayback_url: str = DEFAULT_ARCHIVE_IT_WAYBACK_URL,
        page_size: int = DEFAULT_ARCHIVE_IT_PAGE_SIZE,
        priority: float | None = None,
        no_merge: bool = False,
        auto_merge: bool = False,
) -> None:
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
            for metadata_field in _ARCHIVE_IT_METADATA_FIELDS:
                if metadata_field in metadata:
                    for title in metadata[metadata_field]:
                        description_parts.append(
                            f"{metadata_field}: {title['value']}")
            description_parts.append(f"Archive-It ID: {archive_it_id}")
            description = "\n".join(description_parts)
            cdx_api_url = urljoin(
                wayback_url, f"{archive_it_id}/timemap/cdx")
            memento_api_url = urljoin(wayback_url, f"{archive_it_id}")
            add_archive(
                config=config,
                name=name,
                description=description,
                cdx_api_url=cdx_api_url,
                memento_api_url=memento_api_url,
                priority=priority,
                no_merge=no_merge,
                auto_merge=auto_merge,
            )
            progress.update(1)
