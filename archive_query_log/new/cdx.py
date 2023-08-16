from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property
from json import loads
from typing import Iterator, NamedTuple
from urllib.parse import urlsplit
from warnings import warn

from click import echo
from dateutil.tz import UTC
from requests import Session, Response
from tqdm.auto import tqdm


@dataclass(frozen=True)
class CdxCapture:
    url: str
    url_key: str
    timestamp: datetime
    mimetype: str
    status_code: int
    digest: str
    filename: str | None
    offset: int | None
    length: int | None
    flags: set[str] | None
    collection: str | None
    source: str | None
    source_collection: str | None


class CdxMatchType(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    HOST = "host"
    DOMAIN = "domain"


class _CdxApiType(Enum):
    INTERNET_ARCHIVE = "internet_archive"
    PYWB = "pywb"


_API_TYPE_LOOKUP_NETLOC = {
    "web.archive.org": _CdxApiType.INTERNET_ARCHIVE,
}


class _CdxResponse(NamedTuple):
    resume_key: str | None
    json: list[dict]


def _parse_cdx_line(line: dict) -> CdxCapture:
    line = {
        key: value if value != "-" else None
        for key, value in line.items()
    }
    if "urlkey" in line:
        url_key = line.pop("urlkey")
    else:
        raise ValueError(f"Missing URL key in CDX line: {line}")
    if "timestamp" in line:
        timestamp = datetime.strptime(
            line.pop("timestamp"),
            "%Y%m%d%H%M%S"
        )
    else:
        raise ValueError(f"Missing timestamp in CDX line: {line}")
    if "url" in line:
        url = line.pop("url")
    elif "original" in line:
        url = line.pop("original")
    else:
        raise ValueError(f"Missing url in CDX line: {line}")
    if "mimetype" in line:
        mimetype = line.pop("mimetype")
    elif "mime" in line:
        mimetype = line.pop("mime")
    else:
        raise ValueError(f"Missing mime type in CDX line: {line}")
    if "statuscode" in line:
        statuscode_string = line.pop("statuscode")
        status_code = int(statuscode_string) \
            if statuscode_string is not None else None
    elif "status" in line:
        statuscode_string = line.pop("status")
        status_code = int(statuscode_string) \
            if statuscode_string is not None else None
    else:
        raise ValueError(f"Missing status code in CDX line: {line}")
    if "digest" in line:
        digest = line.pop("digest")
    else:
        raise ValueError(f"Missing digest in CDX line: {line}")
    if "filename" in line:
        filename = line.pop("filename")
    else:
        filename = None
    if "offset" in line:
        offset_string = line.pop("offset")
        offset = int(offset_string) if offset_string is not None else None
    else:
        offset = None
    if "length" in line:
        length_string = line.pop("length")
        length = int(length_string) if length_string is not None else None
    else:
        length = None
    if "flags" in line:
        flags = set(line.pop("flags").split())
    else:
        flags = None
    if "collection" in line:
        collection = line.pop("collection")
    else:
        collection = None
    if "source" in line:
        source = line.pop("source")
    else:
        source = None
    if "source-coll" in line:
        source_collection = line.pop("source-coll")
    else:
        source_collection = None

    # TODO: Unparsed fields in CDX line: {'redirect': None, 'robotflags': None, 'load_url': '', 'access': 'allow'}
    if len(line) > 0:
        warn(RuntimeWarning(f"Unparsed fields in CDX line: {line}"))
    return CdxCapture(
        url=url,
        url_key=url_key,
        timestamp=timestamp,
        mimetype=mimetype,
        status_code=status_code,
        digest=digest,
        filename=filename,
        offset=offset,
        length=length,
        flags=flags,
        collection=collection,
        source=source,
        source_collection=source_collection,
    )


def _parse_cdx_lines(json: list[dict]) -> Iterator[CdxCapture]:
    for line in json:
        yield _parse_cdx_line(line)


def _read_response(response: Response) -> _CdxResponse:
    response.raise_for_status()

    lines: list[str] = response.text.splitlines()
    if len(lines) == 0:
        return _CdxResponse(resume_key=None, json=[])

    json: list[list] | list[dict]
    if lines[0].startswith("[["):
        # Internet Archive style JSON CDX.
        json = response.json()
    else:
        json = [loads(line) for line in lines]

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
    api_url: str
    session: Session

    @cached_property
    def api_type(self) -> _CdxApiType | None:
        scheme, netloc, path, query, fragment = urlsplit(self.api_url)
        if netloc in _API_TYPE_LOOKUP_NETLOC:
            return _API_TYPE_LOOKUP_NETLOC[netloc]
        return None

    def iter_captures(
            self,
            url: str,
            match_type: CdxMatchType | None = None,
            from_timestamp: datetime | None = None,
            to_timestamp: datetime | None = None,
    ) -> Iterator[CdxCapture]:
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

        echo(f"Parsing {self.api_url}?url={url}&matchType={match_type.value}")
        params = [
            ("url", url),
            ("output", "json"),
        ]
        if match_type is not None:
            params.append(("matchType", match_type.value))
        if from_timestamp is not None:
            params.append(("from", from_timestamp.astimezone(UTC)
                           .strftime("%Y%m%d%H%M%S")))
        if to_timestamp is not None:
            params.append(("to", to_timestamp.astimezone(UTC)
                           .strftime("%Y%m%d%H%M%S")))

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
            pages = range(num_pages)
            if num_pages > 10:
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
