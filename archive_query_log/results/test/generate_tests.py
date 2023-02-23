from collections import defaultdict
from gzip import GzipFile
from io import TextIOWrapper, BytesIO
from json import loads
from math import inf
from pathlib import Path
from random import Random
from re import compile
from textwrap import dedent
from typing import Iterable

from requests import get
from slugify import slugify
from tqdm import tqdm
from warcio import WARCWriter, StatusAndHeaders

from archive_query_log import PROJECT_DIRECTORY_PATH
from archive_query_log.config import SERVICES
from archive_query_log.model import Service, ArchivedQueryUrl

NUM_SERVICES = 11
SERVICE_NAMES = None
# SERVICE_NAMES = ["wikimedia"]
NUM_QUERIES_PER_SERVICE = 10

DATA_PATH = Path(
    "/mnt/ceph/storage/data-in-progress/data-research/"
    "web-search/web-archive-query-log/focused/"
)

SAMPLE_QUERIES_PATH = DATA_PATH / "sample-corpus" / "queries-2023-02-17"

WARCS_PATH = PROJECT_DIRECTORY_PATH / \
             "data/manual-annotations/archived-raw-serps/warcs/"
TESTS_PATH = PROJECT_DIRECTORY_PATH / \
             "archive_query_log/results/test/"

PATTERN_SPECIAL_CHARS = compile(r"[^0-9a-z]+")


def main():
    if SERVICE_NAMES is None:
        services: Iterable[Service] = SERVICES.values()
        services = sorted(
            services,
            key=lambda s: s.alexa_rank if s.alexa_rank is not None else inf,
        )
        services = services[:NUM_SERVICES]
        service_names = [s.name for s in services]
    else:
        service_names = SERVICE_NAMES

    query_urls = defaultdict(list)
    for path in tqdm(list(SAMPLE_QUERIES_PATH.glob("part*.gz"))):
        # noinspection PyTypeChecker
        with GzipFile(path, "rb") as gf, TextIOWrapper(gf) as f:
            for line in f:
                if "\"archived_query_url_location\": {" not in line:
                    continue
                query_url = loads(line)
                query_urls[query_url["service"]].append(query_url)

    query_urls = {
        service_name: Random(0).sample(
            query_urls[service_name], min(
                NUM_QUERIES_PER_SERVICE,
                len(query_urls[service_name]),
            )
        )
        for service_name in service_names
    }

    print("Generate WARC files.")
    schema = ArchivedQueryUrl.schema()
    for service_name in service_names:
        for query_url in tqdm(
                query_urls[service_name], desc=service_name
        ):
            query = query_url["url_query"]
            query = slugify(query)
            query = query[:100]
            name = slugify(
                f"{service_name}-"
                f"{query}-{query_url['timestamp']}"
            )
            warc_path = WARCS_PATH / f"{name}.warc.gz"
            if warc_path.exists():
                continue
            with warc_path.open("wb") as o:
                writer = WARCWriter(o, gzip=True)
                archived_query_url = ArchivedQueryUrl(
                    url=query_url["url"],
                    timestamp=int(query_url["timestamp"]),
                    query=query_url["url_query"],
                    page=query_url["url_page"],
                    offset=query_url["url_offset"],
                )
                url_headers = {
                    "Archived-URL": schema.dumps(archived_query_url),
                }
                wayback_raw_url = query_url["wayback_raw_url"]
                response = get(
                    wayback_raw_url,
                )
                if response.status_code != 200:
                    raise

                # noinspection PyProtectedMember
                version = str(response.raw.version)
                protocol = f"HTTP/{version[0]}.{version[1]}"
                request_record = writer.create_warc_record(
                    uri=str(response.request.url),
                    record_type="request",
                    http_headers=StatusAndHeaders(
                        statusline=" ".join((
                            response.request.method,
                            response.request.path_url,
                            protocol,
                        )),
                        headers=response.request.headers,
                        protocol=protocol,
                    ),
                    warc_headers_dict={**url_headers},
                )
                writer.write_record(request_record)
                response_record = writer.create_warc_record(
                    uri=str(response.url),
                    record_type="response",
                    http_headers=StatusAndHeaders(
                        statusline=" ".join((
                            protocol,
                            str(response.status_code),
                            response.reason,
                        )),
                        headers=response.headers,
                        protocol=protocol
                    ),
                    payload=BytesIO(response.content),
                    length=len(response.content),
                    warc_headers_dict={**url_headers},
                )
                writer.write_record(response_record)

    print("Generate test files.")
    for service_name in service_names:
        if len(query_urls[service_name]) == 0:
            continue
        test_path = TESTS_PATH / f"test_{service_name}_serp_parsing.py"
        if not test_path.exists():
            with test_path.open("wt") as o:
                o.write(dedent("""
                # flake8: noqa
                # This file is auto-generated by generate_tests.py.
                """).lstrip())
                o.write(dedent("""
                from archive_query_log.results.test.test_utils import verify_serp_parsing
                """).lstrip())
        with test_path.open("rt") as f:
            existing_tests = {
                line.removeprefix("def test_parse_query_").removesuffix("():")
                for line in f
                if line.startswith("def test_parse_query_")
            }
        with test_path.open("at") as o:
            for query_url in query_urls[service_name]:
                wayback_raw_url = query_url["wayback_raw_url"]

                query = query_url["url_query"]
                query = slugify(query)
                query = query[:100]
                name = slugify(
                    f"{service_name}_{query}_{query_url['timestamp']}",
                    separator="_",
                )
                wayback_raw_url_safe = wayback_raw_url.replace('"', '\\"')

                if name in existing_tests:
                    continue
                o.write(dedent(f"""

                def test_parse_query_{name}():
                    verify_serp_parsing(
                        "{wayback_raw_url_safe}",
                        "{service_name}",
                    )
                """))


if __name__ == '__main__':
    main()
