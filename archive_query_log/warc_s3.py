from configparser import ConfigParser
from dataclasses import dataclass
from functools import cached_property
from gzip import open as gzip_open, GzipFile
from itertools import chain
from pathlib import Path
from tempfile import TemporaryFile
from types import TracebackType
from typing import ContextManager, IO, NamedTuple, Iterable, Iterator, \
    Generator
from uuid import uuid4
from warnings import warn

from boto3 import Session
from more_itertools import spy
from mypy_boto3_s3 import S3Client
from tqdm.auto import tqdm
from warcio import ArchiveIterator, WARCWriter
from warcio.recordloader import ArcWarcRecord as WarcRecord

_S3CFG_PATH = Path("~/.s3cfg").expanduser()

_DEFAULT_MAX_FILE_SIZE = 1_000_000_000  # 1GB


class WarcS3Location(NamedTuple):
    endpoint_url: str
    bucket: str
    key: str
    offset: int


def _write_records(
        records: Iterable[WarcRecord],
        file: IO[bytes],
        file_name: str,
        max_size: int,
) -> Generator[int, None, Iterator[WarcRecord]]:
    # Write WARC info record.
    with GzipFile(fileobj=file, mode="wb") as gzip_file:
        writer = WARCWriter(gzip_file, gzip=False)
        warc_info_record: WarcRecord = writer.create_warcinfo_record(
            filename=file_name, info={})
        writer.write_record(warc_info_record)

    # Warn about low max file size.
    if file.tell() * 2 > max_size:
        warn(UserWarning(f"Very low max file size: {max_size} bytes"))

    # Peek at first record.
    head: list[WarcRecord]
    head, records = spy(records)

    # No records to write.
    if len(head) == 0:
        return records

    for record in records:
        offset = file.tell()
        with TemporaryFile() as tmp_file:
            # Write record to temporary file.
            with GzipFile(fileobj=tmp_file, mode="wb") as tmp_gzip_file:
                writer = WARCWriter(tmp_gzip_file, gzip=False)
                writer.write_record(record)
            tmp_file.flush()
            tmp_size = tmp_file.tell()
            tmp_file.seek(0)

            # Check if record fits into file.
            if offset + tmp_size > max_size:
                records = chain([record], records)
                break

            # Write temporary file to file.
            file.write(tmp_file.read())
            yield offset

    return records


# TODO: Remove this test function.
def _test_iterator() -> Iterator[WarcRecord]:
    repetitions = 10000
    for i in range(repetitions):
        with gzip_open(
                "/home/heinrich/Repositories/archive-query-log/data/manual-annotations/archived-raw-serps/warcs/google-does-steve-has-a-beard-1601705030.warc.gz",
                "rb") as file:
            yield from ArchiveIterator(file)

dataclass(frozen=True)
class WarcS3Store(ContextManager):
    bucket_name: str
    endpoint_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    max_file_size: int = _DEFAULT_MAX_FILE_SIZE
    """
    Maximum number of bytes to write to a single WARC file.
    """

    @cached_property
    def config(self) -> ConfigParser:
        config = ConfigParser()
        if _S3CFG_PATH.exists():
            config.read(_S3CFG_PATH)
        return config

    @cached_property
    def client(self) -> S3Client:
        if self.access_key is not None:
            access_key = self.access_key
        elif self.config.has_section("default"):
            access_key = self.config.get("default", "access_key")
        else:
            raise ValueError("No access key provided.")
        if self.secret_key is not None:
            secret_key = self.secret_key
        elif self.config.has_section("default"):
            secret_key = self.config.get("default", "secret_key")
        else:
            raise ValueError("No secret key provided.")
        return Session().client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def _create_bucket_if_needed(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except self.client.exceptions.NoSuchBucket:
            try:
                self.client.create_bucket(Bucket=self.bucket_name)
            except self.client.exceptions.BucketAlreadyOwnedByYou:
                pass
            except self.client.exceptions.BucketAlreadyExists:
                pass

    def _exists_object(self, key: str) -> bool:
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=key,
            )
        except self.client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise e
        return True

    def write(self, records: Iterable[WarcRecord]) -> Iterator[WarcS3Location]:
        records = iter(records)
        head: list[WarcRecord]
        head, records = spy(records)
        while len(head) > 0:
            with TemporaryFile() as tmp_file:
                # Find next available key.
                key: str = f"{uuid4().hex}.warc.gz"
                while self._exists_object(key):
                    key: str = f"{uuid4().hex}.warc.gz"

                # Write records to buffer.
                offsets: Iterable[int] = _write_records(
                    records=records,
                    file=tmp_file,
                    file_name=key,
                    max_size=self.max_file_size
                )
                # noinspection PyTypeChecker
                offsets = tqdm(
                    offsets,
                    desc="Write WARC records to buffer"
                )
                try:
                    offsets = list(offsets)
                except StopIteration as e:
                    records = e.value
                tmp_file.flush()
                tmp_file.seek(0)

                print("Uploading buffer to S3: ", key)
                if self._exists_object(key):
                    raise RuntimeError(f"Key already exists: {key}")
                self.client.upload_fileobj(
                    Fileobj=tmp_file,
                    Bucket=self.bucket_name,
                    Key=key,
                )
                for offset in offsets:
                    yield WarcS3Location(
                        endpoint_url=self.endpoint_url,
                        bucket=self.bucket_name,
                        key=key,
                        offset=offset,
                    )
            head, records = spy(records)

    def __exit__(
            self,
            _exc_type: type[BaseException] | None,
            _exc_value: BaseException | None,
            _traceback: TracebackType | None
    ) -> bool | None:
        self.client.close()
        return True

    # TODO: Remove this test function.
    def test(self):
        self._create_bucket_if_needed()
        iterator = _test_iterator()
        locations = self.write(iterator)
        for _ in locations:
            pass


if __name__ == "__main__":
    store = WarcS3Store(
        endpoint_url="https://s3.dw.webis.de",
        access_key="KFL4B8B3KCCHU0E58SXX",
        secret_key="Bfnchgz0B1C8ie3UJcvfUSlMeXtvFMG6lm5sMZ2t",
        bucket_name="archive-query-log",
    )
    store.test()
