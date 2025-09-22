from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cached_property
from hashlib import md5
from urllib.parse import SplitResult, urlsplit
from uuid import UUID, uuid5, NAMESPACE_URL

from dataclasses_json import DataClassJsonMixin


@dataclass(frozen=True, slots=True)
class ArchivedUrl(DataClassJsonMixin):
    """
    A URL that is archived in the Wayback Machine (https://web.archive.org/).
    The archived snapshot can be retrieved using the ``archive_url``
    and ``raw_archive_url`` properties.

    Output of: 2-archived-urls
    Input of: 3-archived-query-urls
    """

    url: str
    """
    Original URL that was archived.
    """
    timestamp: int
    """
    Timestamp of the archived snapshot in the Wayback Machine.
    """

    @cached_property
    def id(self) -> UUID:
        """
        Unique ID for this archived URL.
        """
        return uuid5(NAMESPACE_URL, f"{self.timestamp}:{self.url}")

    @cached_property
    def split_url(self) -> SplitResult:
        """
        Original URL split into its components.
        """
        return urlsplit(self.url)

    @cached_property
    def url_domain(self) -> str:
        """
        Domain of the original URL.
        """
        return self.split_url.netloc

    @cached_property
    def url_md5(self) -> str:
        """
        MD5 hash of the original URL.
        """
        return md5(self.url.encode(), usedforsecurity=False).hexdigest()

    @cached_property
    def datetime(self) -> datetime:
        """
        Snapshot timestamp as a ``datetime`` object.
        """
        return datetime.fromtimestamp(self.timestamp, timezone.utc)

    @cached_property
    def archive_timestamp(self) -> str:
        """
        Snapshot timestamp as a string in the format used
        by the Wayback Machine (``YYYYmmddHHMMSS``).
        """
        return (
            f"{self.datetime.year:04d}{self.datetime.month:02d}"
            f"{self.datetime.day:02d}{self.datetime.hour:02d}"
            f"{self.datetime.minute:02d}{self.datetime.second:02d}"
        )

    @property
    def archive_url(self) -> str:
        """
        URL of the archived snapshot in the Wayback Machine.
        """
        return f"https://web.archive.org/web/{self.archive_timestamp}/{self.url}"

    @property
    def raw_archive_url(self) -> str:
        """
        URL of the archived snapshot's raw contents in the Wayback Machine.
        """
        return f"https://web.archive.org/web/{self.archive_timestamp}id_/{self.url}"
