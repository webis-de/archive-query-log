from datetime import datetime
from gzip import GzipFile
from json import loads, JSONDecodeError, dumps
from pathlib import Path
from random import shuffle
from typing import Optional, Iterator
from urllib.parse import urlparse
from uuid import uuid5, NAMESPACE_URL

from fastwarc import FileStream, ArchiveIterator, WarcRecordType, WarcRecord
from pyspark.sql import SparkSession
from tqdm.auto import tqdm

_CEPH_DIR = Path("/mnt/ceph/storage")
_RESEARCH_DIR = _CEPH_DIR / "data-in-progress" / "data-research"
_GLOBAL_DATA_DIR = _RESEARCH_DIR / "web-search" / "web-archive-query-log"
_DATA_DIR = _GLOBAL_DATA_DIR / "focused"





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
    print("Finished reading archived URLs.")
    archived_query_urls_index = _read_jsonl(relative_path,
                                            "archived-query-urls")
    print("Finished reading archived query URLs.")
    archived_raw_serps_index = _index_warc(relative_path, "archived-raw-serps")
    print("Finished reading archived raw SERPs (pointers).")

    for record_id, archived_url in archived_query_urls_index.items():
        archived_query_url = archived_query_urls_index[record_id]
        archived_raw_serp_location = archived_raw_serps_index.get(record_id,
                                                                  None)

        yield relative_path, record_id, archived_query_url, \
            archived_raw_serp_location



def _record_to_query(relative_path_record: tuple) -> Optional[str]:
    relative_path, record_id, archived_query_url, archived_raw_serp_location \
        = relative_path_record

    if archived_raw_serp_location is not None:
        print("SERP was already downloaded.")

    url = archived_query_url["url"]
    domain = urlparse(url).hostname
    timestamp = archived_query_url["timestamp"]
    wayback_timestamp = \
        datetime.fromtimestamp(timestamp).strftime("%Y%m%d%H%M%S")
    wayback_raw_url = \
        f"https://web.archive.org/web/{wayback_timestamp}id_/{url}"


    task = {
        "download_url": wayback_raw_url,
        "output_path": str(_GLOBAL_DATA_DIR / "archived-raw-serps" / relative_path / "*.warc.gz"),
    }
    return dumps(task)



def main():
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
    print(f"Selected {len(relative_paths)} paths "
          f"for finding downloadable SERP URLs.")

    print("Export downloadable SERP URL list at archive-query-log-urls/.")
    sc.parallelize(relative_paths, 100) \
        .flatMap(_iter_relative_path_records) \
        .map(_record_to_query) \
        .filter(lambda json: json is not None) \
        .repartition(1) \
        .saveAsTextFile(f"archive-query-log-urls/",
                        compressionCodecClass=
                        "org.apache.hadoop.io.compress.GzipCodec")

    print("Done.")


if __name__ == "__main__":
    main()
