from io import TextIOWrapper
from shutil import copyfileobj
from tempfile import TemporaryFile
from typing import Literal, Type, TypeVar, Iterable, MutableSequence
from warnings import warn

from cssselect import GenericTranslator
from cssselect.parser import parse as cssselect_parse
from lxml.etree import (
    parse as etree_parse,
    XMLParser,
    HTMLParser,
    _ElementTree,
    _Element,
    XPath,
)
from resiliparse.parse import detect_encoding
from warcio.recordloader import ArcWarcRecord

XmlParserType = Literal[
    "xml",
    "html",
]


def parse_xml_tree(record: ArcWarcRecord) -> _ElementTree | None:
    mime_type: str | None = record.http_headers.get_header("Content-Type")
    if mime_type is None:
        warn("No MIME type given.", UserWarning)
        return None
    mime_type = mime_type.split(";", maxsplit=1)[0]

    wayback_url = record.rec_headers.get_header("WARC-Target-URI")

    with TemporaryFile() as tmp_file:
        # Copy the content stream to a temporary file.
        # This is necessary because the content stream is not seekable.
        try:
            copyfileobj(record.content_stream(), tmp_file)
        except AttributeError as e:
            if e.name == "unused_data":
                warn(f"Brotli decompression error: {wayback_url}", UserWarning)
                return None
        tmp_file.seek(0)

        # Detect encoding using Resiliparse, based on the first 10KB bytes .
        encoding_guess_bytes = tmp_file.read(1024 * 10)
        encodings: MutableSequence[str] = [
            detect_encoding(encoding_guess_bytes, from_html_meta=False),
            detect_encoding(encoding_guess_bytes, from_html_meta=True),
        ]

        # Get the encoding from the Content-Type header.
        html_content_type: str = record.http_headers.get_header("Content-Type")
        if (
            html_content_type is not None
            and ";" in html_content_type
            and "charset=" in html_content_type
        ):
            # Extract the charset from the Content-Type header.
            encodings = [
                part.strip().removeprefix("charset=").lower()
                for part in html_content_type.split(";")
                if part.strip().startswith("charset=")
            ] + list(encodings)

        # Add fall-back encodings.
        if "utf-8" in encodings and "utf-8-sig" not in encodings:
            encodings.append("utf-8-sig")

        # Check if any of the candidate encodings is valid.
        encoding: str | None = None
        for encoding in encodings:
            # Build mapping for Python equivalent of windows-874.
            if encoding == "windows-874":
                encoding = "cp874"
            text_file = TextIOWrapper(tmp_file, encoding=encoding)
            try:
                for _ in text_file:
                    pass
            except (UnicodeDecodeError, UnicodeError):
                encoding = None
                tmp_file.seek(0)
                continue
            finally:
                # Detach the TextIOWrapper to avoid closing the underlying file.
                text_file.detach()
            # If the encoding is valid, break the loop.
            break
        if encoding is None:
            warn(
                f"Could not find valid encoding among {', '.join(encodings)}: {wayback_url}",
                UserWarning,
            )
            return None

        # Rewind the temporary file to the beginning.
        tmp_file.seek(0)

        # Decode the first 100 characters to check for XML/HTML content.
        text_file = TextIOWrapper(tmp_file, encoding=encoding)
        try:
            head = text_file.read(100)
        finally:
            # Detach the TextIOWrapper to avoid closing the underlying file.
            text_file.detach()
        if "<" not in head:
            # warn(f"Skipping non-XML document: {wayback_url}", UserWarning)
            return None
        if head[0] in ["{", "[", '"']:
            warn(f"Skipping JSON-like document: {wayback_url}", UserWarning)
            return None

        parser: XMLParser | HTMLParser
        if mime_type == "text/xml":
            parser = XMLParser(encoding=encoding)
        elif mime_type == "text/html":
            parser = HTMLParser(encoding=encoding)
        else:
            warn(f"Cannot find XML parser for MIME type: {mime_type}", UserWarning)
            return None

        tmp_file.seek(0)
        tree = etree_parse(  # noqa: S320
            source=tmp_file,
            parser=parser,
            base_url=wayback_url,
        )
        return tree


_T = TypeVar("_T")


def safe_xpath(
    tree: _ElementTree | _Element,
    xpath: XPath,
    item_type: Type[_T],
) -> list[_T]:
    results = xpath(tree)
    if not isinstance(results, list):
        results = [results]
    if not all(isinstance(result, item_type) for result in results):
        types = ", ".join({str(type(result)) for result in results})
        raise ValueError(
            f"All results of the XPath '{xpath}' results "
            f"must be of type {item_type}, found: {types}"
        )
    return results


_translator = GenericTranslator()


def xpaths_from_css_selector(css_selector: str) -> list[str]:
    if css_selector == ":--self":
        return ["."]
    selectors = cssselect_parse(css_selector)
    return [
        _translator.selector_to_xpath(
            selector,
            prefix="",
            translate_pseudo_elements=True,
        ).replace("/descendant-or-self::*/", "//")
        for selector in selectors
    ]


def merge_xpaths(xpaths: Iterable[str]) -> str:
    return " | ".join(xpaths)


def text_xpath(
    xpath: str,
    attribute: str | None = None,
    text: bool = False,
) -> str:
    if attribute is None and not text:
        raise ValueError("Either an attribute or text=True must be given.")
    if attribute is not None and text:
        raise ValueError("An attribute and text=True are not allowed at the same time.")
    if text:
        return f"{xpath}//text()"
    else:
        return f"{xpath}/@{attribute}"
