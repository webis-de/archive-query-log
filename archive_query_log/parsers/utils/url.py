from urllib.parse import parse_qsl, unquote

from chardet import EncodingEra, detect
from pydantic import AnyHttpUrl
from resiliparse.parse.encoding import map_encoding_to_html5

_ENCODING_PARAMETERS = {"ie", "ei", "ics", "enc", "encoding", "charset", "oe"}
_MIN_DETECTION_CONFIDENCE = 0.1


def _is_decodable(data: bytes, encoding: str) -> bool:
    try:
        data.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return False
    return True


def _parse_raw_parameters(query_string: str) -> list[tuple[str, bytes]]:
    # Surrogate escapes keep invalid UTF-8 bytes, so the original bytes can be restored.
    return [
        (name, value.encode("utf-8", errors="surrogateescape"))
        for name, value in parse_qsl(query_string, errors="surrogateescape")
    ]


def _detect_encoding(value: bytes, parameters: list[tuple[str, bytes]]) -> str:
    # First look for explicit encoding definitions in the parameters.
    for name, declared_value in parameters:
        if name.lower() in _ENCODING_PARAMETERS:
            encoding = map_encoding_to_html5(
                declared_value.decode("utf-8", errors="ignore")
            )
            if _is_decodable(value, encoding):
                return encoding
    # Fall back to chardet encoding detection.
    result = detect(value, encoding_era=EncodingEra.MODERN_WEB)
    # Keep replacement characters rather than risking plausible but wrong text.
    if result["encoding"] is None or result["confidence"] < _MIN_DETECTION_CONFIDENCE:
        return "utf-8"
    return result["encoding"]


def _parse_parameter(parameter: str, query_string: str) -> str | None:
    parameters = _parse_raw_parameters(query_string)
    for name, value in parameters:
        if name == parameter:
            if _is_decodable(value, "utf-8"):
                return value.decode("utf-8")
            return value.decode(_detect_encoding(value, parameters), errors="replace")
    return None


def parse_url_query_parameter(parameter: str, url: AnyHttpUrl) -> str | None:
    if url.query is None:
        return None
    return _parse_parameter(parameter, url.query)


def parse_url_fragment_parameter(parameter: str, url: AnyHttpUrl) -> str | None:
    if url.fragment is None:
        return None
    return _parse_parameter(parameter, url.fragment)


def parse_url_path_segment(segment: int, url: AnyHttpUrl) -> str | None:
    path = url.path
    if path is None:
        return None
    path_segments = path.split("/")
    if len(path_segments) <= segment:
        return None
    path_segment = path_segments[segment]
    return unquote(path_segment)
