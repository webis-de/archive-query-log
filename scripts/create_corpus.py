from argparse import ArgumentParser
from datetime import datetime
from gzip import GzipFile
from json import loads, JSONDecodeError, dumps
from pathlib import Path
from random import shuffle
from typing import Optional, Iterator, Literal
from urllib.parse import urlparse
from uuid import uuid5, NAMESPACE_URL

from fastwarc import FileStream, ArchiveIterator, WarcRecordType, WarcRecord
from publicsuffixlist import PublicSuffixList
from pyspark.sql import SparkSession
from tqdm.auto import tqdm
from yaml import safe_load

_CEPH_DIR = Path("/mnt/ceph/storage")
_RESEARCH_DIR = _CEPH_DIR / "data-in-progress" / "data-research"
_GLOBAL_DATA_DIR = _RESEARCH_DIR / "web-search" / "web-archive-query-log"
_DATA_DIR = _GLOBAL_DATA_DIR / "focused"

_PUBLIC_SUFFIX_LIST = PublicSuffixList()


def _load_services(path: Path) -> dict:
    with path.open("r") as file:
        services_dict = safe_load(file)
    services_list = [(service["name"], service) for service in services_dict]
    assert len({name for name, service in services_list}) == len(services_list)
    services = {
        name: service
        for name, service in services_list
    }
    print(f"Found {len(services)} services.")
    return services


_SERVICES = _load_services(_GLOBAL_DATA_DIR / "selected-services.yaml")


def _detect_language(text: str) -> Optional[str]:
    text = text.replace("\n", " ")
    from cld3 import get_language
    language_prediction = get_language(text)
    if language_prediction is None:
        return None
    return language_prediction.language.split("-")[0] \
        if language_prediction.is_reliable else None


def _read_jsonl(path: Path, base_type: str) -> dict:
    jsonl_path = _DATA_DIR / base_type / path.with_suffix(".jsonl.gz")
    if not jsonl_path.exists():
        return {}
    index = {}
    try:
        with GzipFile(jsonl_path, "r") as gzip_file:
            # noinspection PyTypeChecker
            for line in tqdm(gzip_file, desc="Index JSONL"):
                try:
                    # noinspection PyTypeChecker
                    record = loads(line)
                except:
                    print(f"Could not index {line} at {path}.")
                    continue
                record_id = uuid5(
                    NAMESPACE_URL,
                    f"{record['timestamp']}:{record['url']}",
                )
                index[record_id] = record
        return index
    except:
        print(f"Could not read JSONL file at {path}.")
        return {}


def _index_warc(path: Path, base_type: str) -> dict:
    warc_path = _DATA_DIR / base_type / path
    if not warc_path.exists():
        return {}
    index = {}
    for warc_child_path in warc_path.iterdir():
        if warc_child_path.name.startswith("."):
            continue
        try:
            stream = FileStream(str(warc_child_path.absolute()))
            records = ArchiveIterator(
                stream,
                record_types=WarcRecordType.response,
                parse_http=False,
            )
            # noinspection PyTypeChecker
            for record in tqdm(records, desc="Index WARC"):
                record: WarcRecord
                offset = record.stream_pos
                record_url_header = record.headers["Archived-URL"]
                try:
                    record_url = loads(record_url_header)
                except JSONDecodeError:
                    print(f"Could not index {record_url_header} at {path}.")
                    continue
                record_id = uuid5(
                    NAMESPACE_URL,
                    f"{record_url['timestamp']}:{record_url['url']}",
                )
                index[record_id] = (
                    warc_child_path,
                    offset,
                )
        except:
            print(f"Could not read WARC file at {warc_child_path}.")
            continue
    return index


def _iter_relative_path_records(relative_path: Path) -> Iterator[tuple]:
    service = relative_path.parts[0]

    print(f"Reading files in {relative_path}.")
    archived_urls_index = _read_jsonl(relative_path, "archived-urls")
    print("Finished reading archived URLs.")
    archived_query_urls_index = _read_jsonl(relative_path,
                                            "archived-query-urls")
    print("Finished reading archived query URLs.")
    archived_raw_serps_index = _index_warc(relative_path, "archived-raw-serps")
    print("Finished reading archived raw SERPs (pointers).")
    archived_parsed_serps_index = _read_jsonl(relative_path,
                                              "archived-parsed-serps")
    print("Finished reading archived parsed SERPs.")

    for record_id, archived_url in archived_urls_index.items():
        archived_url = archived_urls_index[record_id]
        archived_query_url = archived_query_urls_index.get(record_id, None)
        archived_raw_serp_location = archived_raw_serps_index.get(record_id,
                                                                  None)
        archived_parsed_serp = archived_parsed_serps_index.get(record_id, None)

        yield service, relative_path, record_id, archived_url, archived_query_url, archived_raw_serp_location, archived_parsed_serp


def _iter_results(
        archived_url: dict, archived_parsed_serp: dict
) -> Iterator[dict]:
    if archived_parsed_serp is None:
        return

    for snippet in archived_parsed_serp["results"]:
        url = snippet["url"]
        domain = urlparse(url).hostname
        public_suffix = _PUBLIC_SUFFIX_LIST.publicsuffix(domain) \
            if domain is not None else None
        timestamp = archived_url["timestamp"]
        wayback_timestamp = \
            datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
        wayback_url = f"https://web.archive.org/web/{wayback_timestamp}/{url}"
        wayback_raw_url = \
            f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"
        record_id = uuid5(
            NAMESPACE_URL,
            f"{snippet['rank']}:{snippet['timestamp']}:{snippet['url']}"
        )
        print(f"Yield result: {record_id}")
        yield {
            "result_id": str(record_id),
            "result_url": url,
            "result_domain": domain,
            "result_domain_public_suffix": public_suffix,
            "result_wayback_url": wayback_url,
            "result_wayback_raw_url": wayback_raw_url,
            "result_snippet_rank": snippet['rank'],
            "result_snippet_title": snippet["title"],
            "result_snippet_text": snippet["snippet"],
            "result_warc_relative_path": None,
            "result_warc_byte_offset": None,
        }


def _record_to_query(relative_path_record: tuple) -> Optional[str]:
    service, relative_path, record_id, archived_url, archived_query_url, \
        archived_raw_serp_location, archived_parsed_serp = relative_path_record

    if archived_query_url is None:
        print(f"Archived query URL not found for ID {record_id}.")
        return None

    url = archived_url["url"]
    domain = urlparse(url).hostname
    public_suffix = _PUBLIC_SUFFIX_LIST.publicsuffix(domain) \
        if domain is not None else None
    timestamp = archived_url["timestamp"]
    wayback_timestamp = \
        datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
    wayback_url = f"https://web.archive.org/web/{wayback_timestamp}/{url}"
    wayback_raw_url = \
        f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"
    query = archived_query_url["query"]
    language = _detect_language(query)
    service_info = _SERVICES[service]

    documents = list(_iter_results(archived_url, archived_parsed_serp))

    print(f"Yield SERP: {record_id}")
    return dumps({
        "serp_id": str(record_id),
        "serp_url": url,
        "serp_domain": domain,
        "serp_domain_public_suffix": public_suffix,
        "serp_timestamp": timestamp,
        "serp_wayback_url": wayback_url,
        "serp_wayback_raw_url": wayback_raw_url,
        "serp_page": archived_query_url["page"],
        "serp_offset": archived_query_url["offset"],
        "serp_query_text_url": query,
        "serp_query_text_url_language": language,
        "serp_query_text_html": (
            archived_parsed_serp["interpreted_query"]
            if archived_parsed_serp is not None else None
        ),
        "serp_warc_relative_path": (
            str(archived_raw_serp_location[0].relative_to(_GLOBAL_DATA_DIR))
            if archived_raw_serp_location is not None else None
        ),
        "serp_warc_byte_offset": (
            archived_raw_serp_location[1]
            if archived_raw_serp_location is not None else None
        ),
        "serp_results": documents,
        "search_provider_name": service,
        "search_provider_alexa_domain": service_info["alexa_domain"],
        "search_provider_alexa_domain_public_suffix":
            _SERVICES[service]["public_suffix"],
        "search_provider_alexa_rank": service_info["alexa_rank"],
        "search_provider_category": service_info["category"],
    })


def _iter_query_documents(query: str) -> Iterator[dict]:
    query = loads(query)
    for result in query["serp_results"]:
        print(f"Yield result: {result['result_id']}")
        yield dumps({
            "result_id": result["result_id"],
            "result_url": result["result_url"],
            "result_domain": result["result_domain"],
            "result_domain_public_suffix":
                result["result_domain_public_suffix"],
            "result_wayback_url": result["result_wayback_url"],
            "result_wayback_raw_url": result["result_wayback_raw_url"],
            "result_snippet_rank": result["result_snippet_rank"],
            "result_snippet_title": result["result_snippet_title"],
            "result_snippet_text": result["result_snippet_text"],
            "result_warc_relative_path": result["result_warc_relative_path"],
            "result_warc_byte_offset": result["result_warc_byte_offset"],
            "serp_id": query["serp_id"],
            "serp_url": query["serp_url"],
            "serp_domain": query["serp_domain"],
            "serp_domain_public_suffix": query["serp_domain_public_suffix"],
            "serp_timestamp": query["serp_timestamp"],
            "serp_wayback_url": query["serp_wayback_url"],
            "serp_wayback_raw_url": query["serp_wayback_raw_url"],
            "serp_page": query["serp_page"],
            "serp_offset": query["serp_offset"],
            "serp_query_text_url": query["serp_query_text_url"],
            "serp_query_text_url_language":
                query["serp_query_text_url_language"],
            "serp_query_text_html": query["serp_query_text_html"],
            "serp_warc_relative_path": query["serp_warc_relative_path"],
            "serp_warc_byte_offset": query["serp_warc_byte_offset"],
            "search_provider_name": query["search_provider_name"],
            "search_provider_alexa_domain":
                query["search_provider_alexa_domain"],
            "search_provider_alexa_domain_public_suffix":
                query["search_provider_alexa_domain_public_suffix"],
            "search_provider_alexa_rank": query["search_provider_alexa_rank"],
            "search_provider_category": query["search_provider_category"],
        })


def main(variant: Literal["small", "medium", "full"]):
    session = SparkSession.builder.getOrCreate()

    sc = session.sparkContext

    relative_paths = [
        path
        .relative_to(_DATA_DIR / "archived-urls")
        .with_name(path.name[:-len(".jsonl.gz")])
        for path in _DATA_DIR.glob("archived-urls/*/*/*.jsonl.gz")
    ]
    print(f"Found {len(relative_paths)} paths.")
    shuffle(relative_paths)
    if variant == "small":
        relative_paths = relative_paths[:100]
    elif variant == "medium":
        relative_paths = relative_paths[:2500]
    print(f"Selected {len(relative_paths)} paths for corpus creation.")

    print("Start corpus creation.")

    print("Export SERPs.")
    sc.parallelize(relative_paths) \
        .repartition(1_000) \
        .flatMap(_iter_relative_path_records) \
        .map(_record_to_query) \
        .filter(lambda json: json is not None) \
        .saveAsTextFile(f"archive-query-log/{variant}/serps/",
                        compressionCodecClass=
                        "org.apache.hadoop.io.compress.GzipCodec")

    print("Export results.")
    sc.textFile(f"archive-query-log/{variant}/serps/") \
        .flatMap(_iter_query_documents) \
        .map(dumps) \
        .repartition(1_000) \
        .saveAsTextFile(f"archive-query-log/{variant}/results/",
                        compressionCodecClass=
                        "org.apache.hadoop.io.compress.GzipCodec")

    print("Done.")


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--small",
        dest="variant",
        action="store_const",
        const="small",
        default="full",
    )
    parser.add_argument(
        "--medium",
        dest="variant",
        action="store_const",
        const="medium",
        default="full",
    )
    parser.add_argument(
        "--full",
        dest="variant",
        action="store_const",
        const="full",
        default="full",
    )
    args = parser.parse_args()
    print(f"Creating corpus (variant: {args.variant}).")
    main(args.variant)
