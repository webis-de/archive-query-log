from collections import defaultdict
from datetime import datetime, timezone
from gzip import GzipFile
from io import TextIOWrapper, BytesIO
from json import loads
from pathlib import Path
from random import Random
from re import compile as pattern
from textwrap import dedent

from requests import get
from slugify import slugify
from tqdm import tqdm
from warcio import WARCWriter, StatusAndHeaders

from archive_query_log.legacy import PROJECT_DIRECTORY_PATH
from archive_query_log.legacy.model import ArchivedQueryUrl

NUM_SERVICES = 11
SERVICE_NAMES = ["google", "yahoo", "bing", "duckduckgo", "ask", "ecosia"]
NUM_QUERIES_PER_SERVICE = 50

DATA_PATH = Path(
    "/mnt/ceph/storage/data-in-progress/data-research/"
    "web-search/web-archive-query-log/focused/"
)

SAMPLE_QUERIES_PATH = DATA_PATH / "corpus" / "medium" / "2023-05-22" / "serps"

WARCS_PATH = PROJECT_DIRECTORY_PATH / \
             "data/manual-annotations/archived-raw-serps/warcs/"
TESTS_PATH = PROJECT_DIRECTORY_PATH / \
             "archive_query_log/results/test/"

PATTERN_SPECIAL_CHARS = pattern(r"[^0-9a-z]+")


def warc_url(url: str, timestamp: float) -> str:
    wayback_timestamp = datetime \
        .fromtimestamp(timestamp, timezone.utc) \
        .strftime("%Y%m%d%H%M%S")
    wayback_raw_url = \
        f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"
    return wayback_raw_url


def main():
    service_names = SERVICE_NAMES

    query_urls = defaultdict(list)
    for path in tqdm(
            list(SAMPLE_QUERIES_PATH.glob("part*.gz")),
            desc="Load service queries"
    ):
        # noinspection PyTypeChecker
        with GzipFile(path, "rb") as gf, TextIOWrapper(gf) as f:
            for line in f:
                if "\"serp_query_text_url\": \"" not in line:
                    continue
                if "\"serp_warc_relative_path\": \"" not in line:
                    continue
                query_url = loads(line)
                if query_url["search_provider_name"] not in service_names:
                    continue
                query_urls[query_url["search_provider_name"]].append(query_url)

    print(f"Found {sum(len(urls) for urls in query_urls.values())} SERPs.")
    random = Random(0)  # nosec: B311
    query_urls = {
        service_name: random.sample(
            query_urls[service_name], min(
                NUM_QUERIES_PER_SERVICE,
                len(query_urls[service_name]),
            )
        )
        for service_name in service_names
    }
    print(f"Sampled {sum(len(urls) for urls in query_urls.values())} SERPs.")

    print("Generate WARC files.")
    schema = ArchivedQueryUrl.schema()
    for service_name in service_names:
        for query_url in tqdm(
                query_urls[service_name], desc=service_name
        ):
            query = query_url["serp_query_text_url"]
            query = slugify(query)
            query = query[:100]
            name = slugify(
                f"{service_name}-"
                f"{query}-{query_url['serp_timestamp']}"
            )
            warc_path = WARCS_PATH / f"{name}.warc.gz"
            if warc_path.exists():
                continue
            with warc_path.open("wb") as o:
                writer = WARCWriter(o, gzip=True)
                archived_query_url = ArchivedQueryUrl(
                    url=query_url["serp_url"],
                    timestamp=int(query_url["serp_timestamp"]),
                    query=query_url["serp_query_text_url"],
                    page=query_url["serp_page"],
                    offset=query_url["serp_offset"],
                )
                url_headers = {
                    "Archived-URL": schema.dumps(archived_query_url),
                }
                wayback_raw_url = warc_url(
                    query_url["serp_url"],
                    int(query_url["serp_timestamp"]),
                )
                response = get(
                    wayback_raw_url,
                    timeout=60 * 4,  # nosec: B113
                )
                response.raise_for_status()

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
                wayback_raw_url = warc_url(
                    query_url["serp_url"],
                    int(query_url["serp_timestamp"]),
                )

                query = query_url["serp_query_text_url"]
                query = slugify(query)
                query = query[:100]
                name = slugify(
                    f"{service_name}_{query}_{query_url['serp_timestamp']}",
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
