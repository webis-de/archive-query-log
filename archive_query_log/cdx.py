from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from json import loads, JSONDecodeError
from typing import Iterator, NamedTuple, Any, Iterable
from urllib.parse import urlencode, urljoin
from warnings import warn

from requests import Session, Response
from tqdm.auto import tqdm


class CdxFlag(Enum):
    """
    Flags indicating robot instructions found in an HTML page
    or password protection.

    See: https://noarchive.net/
    """
    PASSWORD_PROTECTED = "P"  # nosec: 259
    """
    Non-standard robot flag indicating that the capture is password protected.
    """
    NO_FOLLOW = "F"
    """
    Robot flag indicating that links from the capture should not be followed.
    """
    NO_INDEX = "I"
    """
    Robot flag indicating that the capture should not be indexed.
    """
    NO_ARCHIVE = "A"
    """
    Robot flag indicating that the capture should not be archived/cached.
    """
    IGNORE = "G"
    BLOCKED = "X"
    """
    Non-standard robot flag indicating the capture is soft-blocked
    (not available for direct replay, but available as the original
    for revisits).
    """


@dataclass(frozen=True)
class CdxCapture:
    """
    Single captured document.
    """
    url: str
    """
    Original URL of the captured document.
    """
    url_key: str
    """
    Canonical (lookup key) form of the captured document's URL.
    """
    timestamp: datetime
    """
    Timestamp when the document was captured.
    """
    digest: str
    """
    Some form of document fingerprint. This represents the HTTP payload
    only for HTTP captured resources. It may represent an MD5, a SHA1, and
    may be a fragment of the full representation of the digest.
    """
    status_code: int | None
    """
    HTTP response code (3-digit integer). May be '0' in some
    fringe conditions, old ARCs, bug in crawler, etc.
    """
    mimetype: str | None
    """
    Best guess at the MIME type of the document's content.
    """
    filename: str | None
    """
    Basename of the WARC/ARC file containing the capture.
    """
    offset: int | None
    """
    Compressed byte offset within WARC/ARC file where
    this document's Gzip envelope begins.
    """
    length: int | None
    """
    Compressed length of the document's Gzip envelope.
    """
    access: str | None
    redirect_url: str | None
    """
    URL that this document redirected to.
    """
    flags: set[CdxFlag] | None
    """
    Flags indicating robot instructions found in an HTML page
    or password protection.
    """
    collection: str | None
    source: str | None
    source_collection: str | None


class CdxMatchType(Enum):
    """
    URL matching scope to relax matching of the URL.
    """
    EXACT = "exact"
    """
    Match only the exact URL.
    """
    PREFIX = "prefix"
    """
    Match URLs that start with the given URL.
    """
    HOST = "host"
    """
    Match URLs from the same host as the given URL.
    """
    DOMAIN = "domain"
    """
    Match URLs from the same host or a subhost of the given URL.
    """


class _CdxResponse(NamedTuple):
    """
    Internal representation of a CDX API response,
    optionally including a resume key.
    """
    resume_key: str | None
    json: list[Any]


def _parse_cdx_flags(flags_string: str) -> set[CdxFlag]:
    """
    Parse CDX flags from a string of flags.
    """
    flags = set()
    for flag_string in flags_string.split():
        flag_string = flag_string.strip()
        flag = None
        for candidate_flag in CdxFlag:
            if candidate_flag.value == flag_string:
                flag = candidate_flag
                break
        if flag is not None:
            flags.add(flag)
        else:
            warn(RuntimeWarning(f"Unrecognized CDX flag: {flag_string}"))
    return flags


def _parse_cdx_line(line: dict) -> CdxCapture:
    """
    Parse a single CDX line represented as a JSON dict.
    """
    # Convert "-" to None.
    line = {
        key: value if value != "-" else None
        for key, value in line.items()
    }
    # Parse capture key from 'urlkey' field.
    if "urlkey" in line and line["urlkey"] is not None:
        url_key = line.pop("urlkey")
    else:
        raise ValueError(f"Missing URL key in CDX line: {line}")
    # Parse capture timestamp from 'timestamp' field.
    if "timestamp" in line and line["timestamp"] is not None:
        timestamp = datetime.strptime(
            # Important to add the UTC timezone explicitly.
            f"{line.pop('timestamp')}+0000",
            "%Y%m%d%H%M%S%z"
        )
    else:
        raise ValueError(f"Missing timestamp in CDX line: {line}")
    # Parse original URL from 'url' or 'original' field.
    if "url" in line and line["url"] is not None:
        url = line.pop("url")
    elif "original" in line and line["original"] is not None:
        url = line.pop("original")
    else:
        raise ValueError(f"Missing url in CDX line: {line}")
    # Parse capture digest from 'digest' field.
    if "digest" in line and line["digest"] is not None:
        digest = line.pop("digest")
    else:
        raise ValueError(f"Missing digest in CDX line: {line}")
    # Parse HTTP status code from 'statuscode' or 'status' field.
    if "statuscode" in line:
        status_code_string = line.pop("statuscode")
        if status_code_string is None:
            status_code = None
        else:
            status_code = int(status_code_string)
    elif "status" in line:
        status_code_string = line.pop("status")
        if status_code_string is None:
            status_code = None
        else:
            status_code = int(status_code_string)
    else:
        status_code = None
    # Parse mime type guess from 'mimetype' or 'mime' field.
    if "mimetype" in line:
        mimetype = line.pop("mimetype")
    elif "mime" in line:
        mimetype = line.pop("mime")
    else:
        mimetype = None
    # Parse filename from 'filename' field.
    if "filename" in line:
        filename = line.pop("filename")
    else:
        filename = None
    # Parse Gzip envelope offset from 'offset' field.
    if "offset" in line:
        offset_string = line.pop("offset")
        if offset_string is None:
            offset = None
        else:
            offset = int(offset_string)
    else:
        offset = None
    # Parse Gzip envelope length from 'length' field.
    if "length" in line:
        length_string = line.pop("length")
        if length_string is None:
            length = None
        else:
            length = int(length_string)
    else:
        length = None
    # Parse access policy from 'access' field.
    if "access" in line:
        access = line.pop("access")
    else:
        access = None
    # Parse redirect URL from 'redirect' field.
    if "redirect" in line:
        redirect_url = line.pop("redirect")
    else:
        redirect_url = None
    # Parse flags from 'flags' or 'robotflags' field.
    if "flags" in line:
        flags_string = line.pop("flags")
        if flags_string is None:
            flags = None
        else:
            flags = _parse_cdx_flags(flags_string)
    elif "robotflags" in line:
        flags_string = line.pop("robotflags")
        if flags_string is None:
            flags = None
        else:
            flags = _parse_cdx_flags(flags_string)
    else:
        flags = None
    # Parse collection from 'collection' field.
    if "collection" in line:
        collection = line.pop("collection")
    else:
        collection = None
    # Parse source from 'source' field.
    if "source" in line:
        source = line.pop("source")
    else:
        source = None
    # Parse source collection from 'source-coll' field.
    if "source-coll" in line:
        source_collection = line.pop("source-coll")
    else:
        source_collection = None
    if len(line) > 0:
        # Fail fast if any fields are left unparsed.
        raise RuntimeError(f"Unparsed fields in CDX line: {line}")
    return CdxCapture(
        url=url,
        url_key=url_key,
        timestamp=timestamp,
        status_code=status_code,
        digest=digest,
        mimetype=mimetype,
        filename=filename,
        offset=offset,
        length=length,
        access=access,
        redirect_url=redirect_url,
        flags=flags,
        collection=collection,
        source=source,
        source_collection=source_collection,
    )


def _parse_cdx_lines(json: list[dict]) -> Iterator[CdxCapture]:
    """
    Parse CDX lines represented as a list of JSON dicts.
    """
    for line in json:
        yield _parse_cdx_line(line)


def _read_response(response: Response) -> _CdxResponse:
    """
    Read a raw HTTP response from the CDX API and
    return an internal representation of the response
    after parsing an optional resume key.
    Also unifies the response lines to JSON dicts.
    """
    response.raise_for_status()

    lines: list[str] = response.text.splitlines()
    if len(lines) == 0:
        return _CdxResponse(resume_key=None, json=[])

    json: list[list] | list[dict]
    if lines[0].startswith("[["):
        # Internet Archive style JSON CDX.
        json = response.json()
    else:
        try:
            json = [loads(line) for line in lines]
        except JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse CDX response as JSON: {response.text}"
            ) from e

    if isinstance(json[0], list):
        # Internet Archive style JSON CDX.
        resume_key = None
        if len(lines) >= 3 and len(lines[-1]) == 1 and lines[-2] == []:
            resume_key = lines.pop()[0]
            lines.pop()
        header = json[0]
        json = [dict(zip(header, row)) for row in json[1:]]
        return _CdxResponse(resume_key=resume_key, json=json)
    else:
        return _CdxResponse(resume_key=None, json=json)


@dataclass(frozen=True)
class CdxApi:
    """
    Client to list captured documents from a web archive's CDX API.
    """
    api_url: str
    """
    URL of the CDX API endpoint (e.g. https://web.archive.org/cdx/search/cdx).
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

    def iter_captures(
            self,
            url: str,
            match_type: CdxMatchType,
            from_timestamp: datetime | None = None,
            to_timestamp: datetime | None = None,
    ) -> Iterator[CdxCapture]:
        """
        Query and iterate captures of a URL from the CDX API.
        The returned iterator automatically handles pagination.
        Consuming the iterator eagerly is discouraged.
        :param url: The captured URL (pattern).
        :param match_type: Matching scope to relax URL matching.
        :param from_timestamp: Lower bound for capture timestamps.
        :param to_timestamp: Upper bound for capture timestamps.
        :return: Iterator yielding all captures of the URL.
        """
        # Canonicalize URL and check if the implicit match type
        # matches the explicit match type.
        if url.startswith("*."):
            if match_type != CdxMatchType.DOMAIN:
                raise RuntimeError(
                    f"Implicit match type {CdxMatchType.DOMAIN} conflicts "
                    f"with explicit match type {match_type}."
                )
            url = url[2:]
        if url.endswith("*"):
            if match_type != CdxMatchType.PREFIX:
                raise RuntimeError(
                    f"Implicit match type {CdxMatchType.PREFIX} conflicts "
                    f"with explicit match type {match_type}."
                )
            url = url[:-1]

        # Build query parameters.
        params = [
            ("url", url),
            ("output", "json"),
        ]
        if match_type is not None:
            params.append(("matchType", match_type.value))
        if from_timestamp is not None:
            params.append(("from", from_timestamp.astimezone(timezone.utc)
                           .strftime("%Y%m%d%H%M%S")))
        if to_timestamp is not None:
            params.append(("to", to_timestamp.astimezone(timezone.utc)
                           .strftime("%Y%m%d%H%M%S")))
        if not self.quiet:
            params_encoded = urlencode(params)
            url_joined = urljoin(self.api_url, f"?{params_encoded}")
            print(f"Parsing {url_joined}")

        # Query number of available pages from the CDX API.
        # (This is only available for some CDX API implementations.)
        num_pages = None
        num_pages_response = self.session.get(
            url=self.api_url,
            params=[
                *params,
                ("limit", "1"),
                ("showNumPages", True),
            ],
        )
        if num_pages_response.status_code == 200:
            num_pages_text = num_pages_response.text
            if num_pages_text.strip() != "":
                num_pages_text = num_pages_text.splitlines()[0]
            if num_pages_text.isnumeric():
                num_pages = int(num_pages_text)
        if num_pages is not None:
            # Number of pages is known, so we can iterate over all pages
            # (and show a progress bar).
            pages: Iterable[int] = range(num_pages)
            if num_pages > 10 and not self.quiet:
                # noinspection PyTypeChecker
                pages = tqdm(
                    pages,
                    desc="Read CDX pages",
                    unit="page",
                )
            for page in pages:
                response = self.session.get(
                    url=self.api_url,
                    params=[
                        *params,
                        ("page", page),
                    ],
                )
                _, json = _read_response(response)
                yield from _parse_cdx_lines(json)
        else:
            # Number of pages is unknown, so we request a full list
            # of captures and paginate using the resume key if
            # that is available.
            response = self.session.get(
                url=self.api_url,
                params=[
                    *params,
                    ("showResumeKey", True),
                ],
            )
            resume_key, json = _read_response(response)
            yield from _parse_cdx_lines(json)

            while resume_key is not None:
                response = self.session.get(
                    url=self.api_url,
                    params=[
                        *params,
                        ("resumeKey", resume_key),
                        ("showResumeKey", True),
                    ],
                )
                resume_key, json = _read_response(response)
                yield from _parse_cdx_lines(json)
