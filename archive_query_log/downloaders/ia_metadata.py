from itertools import chain
from typing import Iterable, Iterator
from uuid import uuid5

from elasticsearch_dsl import Search
from elasticsearch_dsl.function import RandomScore
from elasticsearch_dsl.query import FunctionScore, Term, RankFeature, Exists
from tqdm.auto import tqdm

from archive_query_log.config import Config
from archive_query_log.namespaces import NAMESPACE_IA_METADATA_DOWNLOADER
from archive_query_log.orm import Serp, InnerDownloader
from archive_query_log.utils.time import utc_now
from archive_query_log.utils.warc import WarcStore

_DOWNLOADER_ID = uuid5(NAMESPACE_IA_METADATA_DOWNLOADER, "ia_metadata_downloader")


def _normalize_to_list(value) -> list[str] | None:
    if value is None:
        return None
    return [str(value)] if isinstance(value, str) else [str(v) for v in value]


def _extract_ia_identifier(serp: Serp, warc_store: WarcStore) -> str | None:
    if serp.warc_location is None:
        return None
    with warc_store.read(serp.warc_location) as record:
        if record.http_headers is None:
            return None
        src = record.http_headers.get_header("x-archive-src")
    return src.split("/")[0] if src else None


def _fetch_ia_metadata(identifier: str) -> dict | None:
    from internetarchive import get_item
    WANTED_KEYS = {
        "identifier", "collection",
        "contributor", "crawler", "crawljob", "source",
        "mediatype", "publicdate", "addeddate",
        "firstfiledate", "lastfiledate",
        "operator", "sponsor", "uploader", "title",
        "backup_location",
    }
    try:
        item = get_item(identifier)
        if not item.exists:
            return None
        return {k: item.metadata[k] for k in WANTED_KEYS if k in item.metadata}
    except Exception:
        return None


def _download_serp_ia_metadata_action(
    serp: Serp,
    warc_store: WarcStore,
) -> Iterator:
    identifier = _extract_ia_identifier(serp, warc_store)
    metadata = _fetch_ia_metadata(identifier) if identifier else None

    m = metadata or {}
    yield serp.update_action(
        ia_identifier=identifier,
        ia_collection=_normalize_to_list(m.get("collection")),
        ia_contributor=m.get("contributor"),
        ia_crawler=m.get("crawler"),
        ia_crawljob=m.get("crawljob"),
        ia_source=m.get("source"),
        ia_mediatype=m.get("mediatype"),
        ia_publicdate=m.get("publicdate"),
        ia_addeddate=m.get("addeddate"),
        ia_firstfiledate=m.get("firstfiledate"),
        ia_lastfiledate=m.get("lastfiledate"),
        ia_operator=m.get("operator"),
        ia_sponsor=m.get("sponsor"),
        ia_uploader=m.get("uploader"),
        ia_title=m.get("title"),
        ia_backup_location=m.get("backup_location"),
        ia_metadata_downloader=InnerDownloader(
            id=_DOWNLOADER_ID,
            should_download=False,
            last_downloaded=utc_now(),
        ),
    )


def download_serps_ia_metadata(
    config: Config,
    size: int = 10,
    dry_run: bool = False,
) -> None:
    config.es.client.indices.refresh(index=config.es.index_serps)
    changed_serps_search: Search = (
        Serp.search(using=config.es.client, index=config.es.index_serps)
        .filter(
            Exists(field="warc_location")
            & ~Term(ia_metadata_downloader__should_download=False)
        )
        .query(
            RankFeature(field="archive.priority", saturation={})
            | RankFeature(field="provider.priority", saturation={})
            | FunctionScore(functions=[RandomScore()])
        )
    )
    num_changed_serps = changed_serps_search.count()
    if num_changed_serps <= 0:
        print("No new/changed SERPs.")
        return

    changed_serps: Iterable[Serp] = changed_serps_search.params(size=size).execute()
    changed_serps = tqdm(
        changed_serps,
        total=num_changed_serps,
        desc="Downloading IA metadata",
        unit="SERP",
    )
    actions = chain.from_iterable(
        _download_serp_ia_metadata_action(serp, config.s3.warc_store)
        for serp in changed_serps
    )
    config.es.bulk(actions=actions, dry_run=dry_run)
