from gzip import GzipFile
from io import TextIOWrapper
from pathlib import Path
from random import Random

from tqdm import tqdm

REVIEW_SAMPLE_SIZE = 1000

DATA_PATH = Path(
    "/mnt/ceph/storage/data-in-progress/data-research/"
    "web-search/web-archive-query-log/focused/"
)

SAMPLE_CORPUS_PATH = DATA_PATH / "sample-corpus"
SAMPLE_QUERIES_PATH = SAMPLE_CORPUS_PATH / "queries"
SAMPLE_DOCUMENTS_PATH = SAMPLE_CORPUS_PATH / "documents"

REVIEW_SAMPLE_CORPUS_PATH = DATA_PATH / "review-corpus-unfiltered"
REVIEW_SAMPLE_CORPUS_PATH.mkdir(exist_ok=True)
REVIEW_SAMPLE_QUERIES_PATH = REVIEW_SAMPLE_CORPUS_PATH / "queries.jsonl"
REVIEW_SAMPLE_DOCUMENTS_PATH = REVIEW_SAMPLE_CORPUS_PATH / "documents.jsonl"


def main():
    lines = []
    for path in tqdm(list(SAMPLE_QUERIES_PATH.glob("part*.gz"))):
        # noinspection PyTypeChecker
        with GzipFile(path, "rb") as gf, TextIOWrapper(gf) as f:
            for line in f:
                if "\"archived_query_url_location\": {" not in line:
                    continue
                if "\"archived_raw_serp_location\": {" not in line:
                    continue
                # if "\"archived_parsed_serp_location\": {" not in line:
                #     continue
                lines.append(line)

    random = Random(0)  # nosec: B311
    lines = random.sample(lines, REVIEW_SAMPLE_SIZE)

    with REVIEW_SAMPLE_QUERIES_PATH.open("wt") as o:
        for line in lines:
            o.write(line)


if __name__ == '__main__':
    main()
