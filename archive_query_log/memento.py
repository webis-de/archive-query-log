from dataclasses import dataclass
from datetime import datetime, timezone
from typing import overload, Iterator
from urllib.parse import urljoin
from warnings import warn

from requests import Session, Response
from warcio.archiveiterator import ArchiveIterator
from warcio.capture_http import capture_http
from warcio.recordloader import ArcWarcRecord

from archive_query_log.cdx import CdxCapture


@dataclass(frozen=True)
class MementoApi:
    """
    Client to download captured documents from a web archive's Memento API.
    """
    api_url: str
    """
    URL of the Memento API endpoint (e.g. https://web.archive.org/web/).
    """
    session: Session = Session()
    """
    HTTP session to use for requests.
    (Useful for setting headers, proxies, rate limits, etc.)
    """
    quiet: bool = False
    """
    Suppress all output and progress bars.
    """

    @overload
    def load_capture(
            self,
            url_or_cdx_capture: str,
            timestamp: datetime | None = None,
    ) -> Response:
        """
        Load a captured document from the Memento API.
        :param url_or_cdx_capture: The original URL of the document.
        :param timestamp: Timestamp of the capture.
        :return: HTTP response.
        """

    @overload
    def load_capture(
            self,
            url_or_cdx_capture: CdxCapture,
    ) -> Response:
        """
        Load a captured document from the Memento API.
        :param url_or_cdx_capture: The CDX record describing the capture.
        :return: HTTP response.
        """

    def load_capture(
            self,
            url_or_cdx_capture: str | CdxCapture,
            timestamp: datetime | None = None,
    ) -> Response:
        """
        Load a captured document from the Memento API.
        :param url_or_cdx_capture: The original URL of the document
          or a CDX record describing the capture.
        :param timestamp: Timestamp of the capture.
        :return: HTTP response.
        """
        return self._load_capture(url_or_cdx_capture, timestamp)

    def _load_capture(
            self,
            url_or_cdx_capture: str | CdxCapture,
            timestamp: datetime | None,
    ) -> Response:
        if not (isinstance(url_or_cdx_capture, str) or
                isinstance(url_or_cdx_capture, CdxCapture)):
            raise TypeError("URL must be a string or CdxCapture.")
        if isinstance(url_or_cdx_capture, CdxCapture):
            if timestamp is not None:
                warn(UserWarning("Timestamp is ignored for CdxCapture."))
            timestamp = url_or_cdx_capture.timestamp
            url_or_cdx_capture = url_or_cdx_capture.url
        if timestamp is None:
            memento_timestamp = "*"
        else:
            memento_timestamp = (
                timestamp.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"))
        memento_raw_url = urljoin(
            self.api_url, f"{memento_timestamp}id_/{url_or_cdx_capture}")
        response = self.session.get(memento_raw_url)
        response.raise_for_status()
        return response

    @overload
    def load_capture_warc(
            self,
            url_or_cdx_capture: str,
            timestamp: datetime | None = None,
    ) -> Iterator[ArcWarcRecord]:
        """
        Load a captured document from the Memento API and
        capture the HTTP request and response as WARC records.
        :param url_or_cdx_capture: The original URL of the document.
        :param timestamp: Timestamp of the capture.
        :return: Iterator over request and response WARC records.
        """

    @overload
    def load_capture_warc(
            self,
            url_or_cdx_capture: CdxCapture,
    ) -> Iterator[ArcWarcRecord]:
        """
        Load a captured document from the Memento API and
        capture the HTTP request and response as WARC records.
        :param url_or_cdx_capture: The CDX record describing the capture.
        :return: Iterator over request and response WARC records.
        """

    def load_capture_warc(
            self,
            url_or_cdx_capture: str | CdxCapture,
            timestamp: datetime | None = None,
    ) -> Iterator[ArcWarcRecord]:
        """
        Load a captured document from the Memento API and
        capture the HTTP request and response as WARC records.
        :param url_or_cdx_capture: The original URL of the document
          or a CDX record describing the capture.
        :param timestamp: Timestamp of the capture.
        :return: Iterator over request and response WARC records.
        """
        with capture_http() as writer:
            self._load_capture(url_or_cdx_capture, timestamp)
            yield from ArchiveIterator(writer.get_stream())
