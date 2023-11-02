from configparser import ConfigParser
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from functools import cached_property
from gzip import GzipFile
from itertools import chain
from pathlib import Path
from tempfile import TemporaryFile
from typing import IO, NamedTuple, Iterable, Iterator
from uuid import uuid4
from warnings import warn

from boto3 import Session
from more_itertools import spy, before_and_after
from mypy_boto3_s3 import S3Client
from tqdm.auto import tqdm
from warcio import ArchiveIterator, WARCWriter
from warcio.recordloader import ArcWarcRecord as WarcRecord

_S3CFG_PATH = Path("~/.s3cfg").expanduser()

_DEFAULT_MAX_FILE_SIZE = 1_000_000_000  # 1GB


class WarcS3Location(NamedTuple):
    key: str
    offset: int
    length: int


class WarcS3Record(NamedTuple):
    record: WarcRecord
    location: WarcS3Location


class _WarcS3Record(NamedTuple):
    record: WarcRecord
    location: WarcS3Location | None


def _write_records(
        records: Iterable[WarcRecord],
        file: IO[bytes],
        key: str,
        max_size: int,
) -> Iterator[_WarcS3Record]:
    # Write WARC info record.
    with GzipFile(fileobj=file, mode="wb") as gzip_file:
        writer = WARCWriter(gzip_file, gzip=False)
        warc_info_record: WarcRecord = writer.create_warcinfo_record(
            filename=key, info={})
        writer.write_record(warc_info_record)

    # Warn about low max file size.
    if file.tell() * 2 > max_size:
        warn(UserWarning(f"Very low max file size: {max_size} bytes"))

    for record in records:
        offset = file.tell()
        with TemporaryFile() as tmp_file:
            # Write record to temporary file.
            with GzipFile(fileobj=tmp_file, mode="wb") as tmp_gzip_file:
                writer = WARCWriter(tmp_gzip_file, gzip=False)
                writer.write_record(record)
            tmp_file.flush()
            length = tmp_file.tell()
            tmp_file.seek(0)

            # Check if record does not into file.
            if offset + length > max_size:
                records = chain([record], records)
                break

            # Write temporary file to file.
            file.write(tmp_file.read())

            rec = _WarcS3Record(
                record=record,
                location=WarcS3Location(
                    key=key,
                    offset=offset,
                    length=length,
                ),
            )
            yield rec

    for record in records:
        yield _WarcS3Record(record=record, location=None)


@dataclass(frozen=True)
class WarcS3Store(AbstractContextManager):
    bucket_name: str
    endpoint_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    max_file_size: int = _DEFAULT_MAX_FILE_SIZE
    """
    Maximum number of bytes to write to a single WARC file.
    """
    quiet: bool = False
    """
    Suppress logging and progress bars.
    """

    def __post_init__(self):
        self._create_bucket_if_needed()

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

    def write(self, records: Iterable[WarcRecord]) -> Iterator[WarcS3Record]:
        records = iter(records)
        head: list[WarcRecord]
        head, records = spy(records)
        while len(head) > 0:
            with TemporaryFile() as tmp_file:
                # Find next available key.
                key: str = f"{uuid4().hex}.warc.gz"
                while self._exists_object(key):
                    key = f"{uuid4().hex}.warc.gz"

                # Write records to buffer.
                offset_records: Iterable[_WarcS3Record] = _write_records(
                    records=records,
                    file=tmp_file,
                    key=key,
                    max_size=self.max_file_size
                )
                # noinspection PyTypeChecker
                offset_records = tqdm(
                    offset_records,
                    desc="Write WARC records to buffer",
                    disable=self.quiet,
                )
                saved_records, unsaved_records = before_and_after(
                    lambda record: record.location is not None,
                    offset_records,
                )
                # Consume iterator to write records to buffer.
                saved_records = iter(list(saved_records))
                tmp_file.flush()
                tmp_file.seek(0)

                if not self.quiet:
                    print("Uploading buffer to S3: ", key)
                if self._exists_object(key):
                    raise RuntimeError(f"Key already exists: {key}")
                self.client.upload_fileobj(
                    Fileobj=tmp_file,
                    Bucket=self.bucket_name,
                    Key=key,
                )
            for offset_record in saved_records:
                if offset_record.location is None:
                    raise RuntimeError("Expected location to be set.")
                yield WarcS3Record(
                    record=offset_record.record,
                    location=offset_record.location,
                )
            records = (
                offset_record.record
                for offset_record in unsaved_records
            )
            head, records = spy(records)

    @contextmanager
    def read(self, location: WarcS3Location) -> Iterator[WarcRecord]:
        end_offset = location.offset + location.length - 1
        response = self.client.get_object(
            Bucket=self.bucket_name,
            Key=location.key,
            Range=f"bytes={location.offset}-{end_offset}",
        )
        with GzipFile(fileobj=response["Body"], mode="rb") as gzip_file:
            iterator = ArchiveIterator(gzip_file)
            yield next(iterator)

    def __exit__(self, *_exc_details):
        self.client.close()
