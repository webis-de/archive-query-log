from datetime import datetime
from gzip import GzipFile
from json import loads, JSONDecodeError, dumps
from os import environ
from pathlib import Path
from random import shuffle
from subprocess import call
from typing import Optional, Iterator
from urllib.parse import urlparse
from uuid import uuid5, NAMESPACE_URL, UUID

from fastwarc import FileStream, ArchiveIterator, WarcRecordType, WarcRecord
from publicsuffixlist import PublicSuffixList
from pyspark.sql import SparkSession
from tqdm import tqdm
from yaml import safe_load

SAMPLE_CORPUS = False
# SAMPLE_CORPUS = True

ceph_dir = Path("/mnt/ceph/storage")
research_dir = ceph_dir / "data-in-progress" / "data-research"
global_data_dir = research_dir / "web-search" / "web-archive-query-log"
data_dir = global_data_dir / "focused"

environ["PYSPARK_PYTHON"] = str(global_data_dir / "venv/bin/python")
session = SparkSession.builder.getOrCreate()

sc = session.sparkContext
print(sc)

relative_paths = [
    path
    .relative_to(data_dir / "archived-urls")
    .with_name(path.name[:-len(".jsonl.gz")])
    for path in tqdm(
        data_dir.glob("archived-urls/*/*/*.jsonl.gz"),
        desc="Find paths",
        unit="file",
    )
]
shuffle(relative_paths)
if SAMPLE_CORPUS:
    relative_paths = relative_paths[:1000]
print(f"Found {len(relative_paths)} paths.")

with Path("../data/selected-services.yaml").open("r") as file:
    services_dict = safe_load(file)
services_list = [(service["name"], service) for service in services_dict]
assert len({name for name, service in services_list}) == len(services_list)
services = {
    name: service
    for name, service in services_list
}
print(f"Found {len(services)} services.")


def detect_language(text: str) -> Optional[str]:
    text = text.replace("\n", " ")
    from cld3 import get_language
    language_prediction = get_language(text)
    if language_prediction is None:
        return None
    return language_prediction.language.split("-")[0] \
        if language_prediction.is_reliable else None


public_suffix_list = PublicSuffixList()


def relative_path_record_ids(relative_path: Path) -> Iterator[tuple]:
    service = relative_path.parts[0]

    jsonl_path = data_dir / "archived-query-urls" / \
                 relative_path.with_suffix(".jsonl.gz")
    if not jsonl_path.exists():
        return
    with GzipFile(jsonl_path, "r") as gzip_file:
        for i, line in enumerate(tqdm(gzip_file, desc="Read IDs from JSONL")):
            if SAMPLE_CORPUS and i > 100:
                break
            try:
                record = loads(line)
                record_id = uuid5(
                    NAMESPACE_URL,
                    f"{record['timestamp']}:{record['url']}"
                )
                yield service, relative_path, record_id
            except:
                print(f"Could not index {line} at {relative_path}.")


def _relative_path_record_id_base(relative_path_record_id: tuple) -> tuple:
    service: str
    relative_path: Path
    record_id: UUID
    service, relative_path, record_id = relative_path_record_id

    archived_url: Optional[dict] = None
    jsonl_path = data_dir / "archived-urls" / \
                 relative_path.with_suffix(".jsonl.gz")
    if jsonl_path.exists():
        try:
            with GzipFile(jsonl_path, "r") as gzip_file:
                for line in tqdm(
                        gzip_file, desc="Read archived URLs from JSONL"
                ):
                    offset = gzip_file.tell()
                    try:
                        record = loads(line)
                    except:
                        print(f"Could not read JSON record {line} "
                              f"at {relative_path}.")
                        continue
                    if record_id == uuid5(
                            NAMESPACE_URL,
                            f"{record['timestamp']}:{record['url']}"
                    ):
                        archived_url = record
                        break
        except:
            print(f"Could not read JSONL file at {relative_path}.")

    archived_query_url: Optional[dict] = None
    jsonl_path = data_dir / "archived-query-urls" / \
                 relative_path.with_suffix(".jsonl.gz")
    if jsonl_path.exists():
        try:
            with GzipFile(jsonl_path, "r") as gzip_file:
                for line in tqdm(
                        gzip_file, desc="Read archived query URLs from JSONL"
                ):
                    try:
                        record = loads(line)
                    except:
                        print(f"Could not read JSON record {line} "
                              f"at {relative_path}.")
                        continue
                    if record_id == uuid5(
                            NAMESPACE_URL,
                            f"{record['timestamp']}:{record['url']}"
                    ):
                        archived_query_url = record
                        break
        except:
            print(f"Could not read JSONL file at {relative_path}.")

    archived_raw_serp_location: Optional[tuple] = None
    warc_path = data_dir / "archived-raw-serps" / relative_path
    if warc_path.exists():
        for warc_child_path in warc_path.iterdir():
            if warc_child_path.name.startswith("."):
                continue
            try:
                stream = FileStream(str(warc_child_path.absolute()))
                # noinspection PyTypeChecker
                records: Iterator[WarcRecord] = ArchiveIterator(
                    stream,
                    record_types=WarcRecordType.response,
                    parse_http=False,
                )
                for record in tqdm(records, desc="Read raw SERPs from WARC"):
                    offset = record.stream_pos
                    record_url_header = record.headers["Archived-URL"]
                    try:
                        record_url = loads(record_url_header)
                    except JSONDecodeError:
                        print(f"Could not read WARC JSON "
                              f"header {record_url_header} "
                              f"at {relative_path}.")
                        continue
                    if record_id == uuid5(
                            NAMESPACE_URL,
                            f"{record_url['timestamp']}:{record_url['url']}"
                    ):
                        archived_raw_serp_location = (warc_child_path, offset)
            except:
                print(f"Could not read WARC file at {warc_child_path}.")

    archived_parsed_serp: Optional[dict] = None
    jsonl_path = data_dir / "archived-parsed-serps" / \
                 relative_path.with_suffix(".jsonl.gz")
    if jsonl_path.exists():
        try:
            with GzipFile(jsonl_path, "r") as gzip_file:
                for line in tqdm(
                        gzip_file, desc="Read parsed SERPs from JSONL"
                ):
                    offset = gzip_file.tell()
                    try:
                        record = loads(line)
                    except:
                        print(f"Could not read JSON record {line} "
                              f"at {relative_path}.")
                        continue
                    if record_id == uuid5(
                            NAMESPACE_URL,
                            f"{record['timestamp']}:{record['url']}"
                    ):
                        archived_parsed_serp = record
                        break
        except:
            print(f"Could not read JSONL file at {relative_path}.")

    return service, relative_path, record_id, archived_url, \
        archived_query_url, archived_raw_serp_location, archived_parsed_serp


def _iter_results(
        archived_url: dict, archived_parsed_serp: dict
) -> Iterator[dict]:
    if archived_parsed_serp is None:
        return

    for snippet in archived_parsed_serp["results"]:
        url = snippet["url"]
        domain = urlparse(url).hostname
        public_suffix = public_suffix_list.publicsuffix(domain)
        timestamp = archived_url["timestamp"]
        wayback_timestamp = \
            datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
        wayback_url = f"https://web.archive.org/web/{wayback_timestamp}/{url}"
        wayback_raw_url = \
            f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"
        yield {
            "result_id": str(uuid5(
                NAMESPACE_URL,
                f"{snippet['rank']}:{snippet['timestamp']}:{snippet['url']}"
            )),
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


def relative_path_record_id_queries(
        relative_path_record_id: tuple
) -> Iterator[dict]:
    service, relative_path, record_id, archived_url, archived_query_url, \
        archived_raw_serp_location, archived_parsed_serp = \
        _relative_path_record_id_base(relative_path_record_id)

    if archived_query_url is None:
        yield "empty"
        print(f"Archived query URL not found for ID {record_id}.")
        return

    url = archived_url["url"]
    domain = urlparse(url).hostname
    public_suffix = public_suffix_list.publicsuffix(domain)
    timestamp = archived_url["timestamp"]
    wayback_timestamp = \
        datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
    wayback_url = f"https://web.archive.org/web/{wayback_timestamp}/{url}"
    wayback_raw_url = \
        f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"
    query = archived_query_url["query"]
    language = detect_language(query)
    service_info = services[service]

    documents = list(_iter_results(archived_url, archived_parsed_serp))

    yield {
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
            str(archived_raw_serp_location[0].relative_to(global_data_dir))
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
            services[service]["public_suffix"],
        "search_provider_alexa_rank": service_info["alexa_rank"],
        "search_provider_category": service_info["category"],
    }


def query_documents(query: dict) -> Iterator[dict]:
    for result in query["serp_results"]:
        yield {
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
        }


call(["hadoop", "fs", "-rm", "-r", "archive-query-log/serps/"])
sc.parallelize(relative_paths) \
    .repartition(1_000) \
    .flatMap(relative_path_record_ids) \
    .repartition(1_000) \
    .flatMap(relative_path_record_id_queries) \
    .map(dumps) \
    .repartition(100) \
    .saveAsTextFile("archive-query-log/serps/",
                    compressionCodecClass=
                    "org.apache.hadoop.io.compress.GzipCodec")

call(["hadoop", "fs", "-rm", "-r", "archive-query-log/results/"])
sc.parallelize(relative_paths) \
    .repartition(1_000) \
    .flatMap(relative_path_record_ids) \
    .repartition(1_000) \
    .flatMap(relative_path_record_id_queries) \
    .flatMap(query_documents) \
    .map(dumps) \
    .repartition(100) \
    .saveAsTextFile("archive-query-log/results/",
                    compressionCodecClass=
                    "org.apache.hadoop.io.compress.GzipCodec")
