from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import cached_property
from json import loads, JSONDecodeError
from typing import Iterator, NamedTuple, Any, Iterable
from urllib.parse import urlsplit
from warnings import warn

from click import echo
from requests import Session, Response
from tqdm.auto import tqdm


class CdxFlag(Enum):
    """
    See:
    https://github.com/iipc/openwayback/blob/98bbc1a6e03f8cb44f00e7505f0e29bccef87abf/wayback-core/src/main/java/org/archive/wayback/core/CaptureSearchResult.java#L97-L120
    """
    PASSWORD_PROTECTED = "P"  # nosec: 259
    NO_FOLLOW = "F"
    NO_INDEX = "I"
    NO_ARCHIVE = "A"
    IGNORE = "G"
    BLOCKED = "X"


@dataclass(frozen=True)
class CdxCapture:
    url: str
    url_key: str
    timestamp: datetime
    digest: str
    status_code: int | None
    mimetype: str | None
    filename: str | None
    offset: int | None
    length: int | None
    access: str | None
    redirect_url: str | None
    flags: set[CdxFlag] | None
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
    json: list[Any]


def _parse_cdx_flags(flags_string: str) -> set[CdxFlag]:
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
    line = {
        key: value if value != "-" else None
        for key, value in line.items()
    }
    if "urlkey" in line and line["urlkey"] is not None:
        url_key = line.pop("urlkey")
    else:
        raise ValueError(f"Missing URL key in CDX line: {line}")
    if "timestamp" in line and line["timestamp"] is not None:
        timestamp = datetime.strptime(
            # Important to add the UTC timezone explicitly.
            f"{line.pop('timestamp')}+0000",
            "%Y%m%d%H%M%S%z"
        )
    else:
        raise ValueError(f"Missing timestamp in CDX line: {line}")
    if "url" in line and line["url"] is not None:
        url = line.pop("url")
    elif "original" in line and line["original"] is not None:
        url = line.pop("original")
    else:
        raise ValueError(f"Missing url in CDX line: {line}")
    if "digest" in line and line["digest"] is not None:
        digest = line.pop("digest")
    else:
        raise ValueError(f"Missing digest in CDX line: {line}")
    if "statuscode" in line and line["statuscode"] is not None:
        status_code = int(line.pop("statuscode"))
    elif "status" in line and line["status"] is not None:
        status_code = int(line.pop("status"))
    else:
        status_code = None
    if "mimetype" in line and line["mimetype"] is not None:
        mimetype = line.pop("mimetype")
    elif "mime" in line and line["mime"] is not None:
        mimetype = line.pop("mime")
    else:
        mimetype = None
    if "filename" in line and line["filename"] is not None:
        filename = line.pop("filename")
    else:
        filename = None
    if "offset" in line and line["offset"] is not None:
        offset = int(line.pop("offset"))
    else:
        offset = None
    if "length" in line and line["length"] is not None:
        length = int(line.pop("length"))
    else:
        length = None
    if "access" in line and line["access"] is not None:
        access = line.pop("access")
    else:
        access = None
    if "redirect" in line and line["redirect"] is not None:
        redirect_url = line.pop("redirect")
    else:
        redirect_url = None
    if "flags" in line and line["flags"] is not None:
        flags = _parse_cdx_flags(line.pop("flags"))
    elif "robotflags" in line and line["robotflags"] is not None:
        flags = _parse_cdx_flags(line.pop("robotflags"))
    else:
        flags = None
    if "collection" in line and line["collection"] is not None:
        collection = line.pop("collection")
    else:
        collection = None
    if "source" in line and line["source"] is not None:
        source = line.pop("source")
    else:
        source = None
    if "source-coll" in line and line["source-coll"] is not None:
        source_collection = line.pop("source-coll")
    else:
        source_collection = None

    # TODO: Unparsed fields in CDX line: {'load_url': ''}
    if len(line) > 0:
        raise RuntimeError(f"Unparsed fields in CDX line: {line}")
        # warn(RuntimeWarning(f"Unparsed fields in CDX line: {line}"))
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
    api_url: str
    session: Session

    @cached_property
    def api_type(self) -> _CdxApiType | None:
        _, netloc, _, _, _ = urlsplit(self.api_url)
        if netloc in _API_TYPE_LOOKUP_NETLOC:
            return _API_TYPE_LOOKUP_NETLOC[netloc]
        return None

    def iter_captures(
            self,
            url: str,
            match_type: CdxMatchType,
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
            params.append(("from", from_timestamp.astimezone(timezone.utc)
                           .strftime("%Y%m%d%H%M%S")))
        if to_timestamp is not None:
            params.append(("to", to_timestamp.astimezone(timezone.utc)
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
            pages: Iterable[int] = range(num_pages)
            if num_pages > 10:
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
