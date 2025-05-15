from io import TextIOWrapper
from shutil import copyfileobj
from tempfile import TemporaryFile
from typing import Literal, Type, TypeVar, Iterable
from warnings import warn

from cssselect import GenericTranslator
from cssselect.parser import parse as cssselect_parse
from lxml.etree import parse as etree_parse, XMLParser, HTMLParser  # nosec: B410
from lxml.etree import _ElementTree, _Element  # nosec: B410
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

    parser: XMLParser | HTMLParser
    if mime_type == "text/xml":
        parser = XMLParser()
    elif mime_type == "text/html":
        parser = HTMLParser()
    else:
        warn(f"Cannot find XML parser for MIME type: {mime_type}", UserWarning)
        return None

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
        encodings: list[str] = list({
            detect_encoding(encoding_guess_bytes, from_html_meta=False),
            detect_encoding(encoding_guess_bytes, from_html_meta=True),
        })

        # Get the encoding from the Content-Type header.
        html_content_type: str = record.http_headers.get_header("Content-Type")
        if html_content_type is not None and ";" in html_content_type and "charset=" in html_content_type:
            # Extract the charset from the Content-Type header.
            encodings.extend({
                part.strip().removeprefix("charset=").lower()
                for part in html_content_type.split(";")
                if part.strip().startswith("charset=")
            }.difference(encodings))

        # Add fall-back encodings.
        if "utf-8" in encodings and "utf-8-sig" not in encodings:
            encodings.append("utf-8-sig")

        # Check if any of the candidate encodings is valid.
        text_file: TextIOWrapper | None = None
        for encoding in encodings:
            # Build mapping for python equivalent of windows-874.
            if encoding == "windows-874":
                encoding = "cp874"
            text_file = TextIOWrapper(tmp_file, encoding=encoding)
            try:
                for _ in text_file:
                    pass
            except (UnicodeDecodeError, UnicodeError):
                tmp_file = text_file.detach()
                text_file = None
                tmp_file.seek(0)
                continue
            # If the encoding is valid, break the loop.
            break
        if text_file is None:
            warn(f"Could not find valid encoding among {', '.join(encodings)}: {wayback_url}", UserWarning)
            return None

        # Decode the first 100 characters to check for XML/HTML content.
        head = text_file.read(100)
        text_file.seek(0)

        if "<" not in head:
            # warn(f"Skipping non-XML document: {wayback_url}", UserWarning)
            return None

        if head[0] in ["{", "[", '"']:
            warn(f"Skipping JSON-like document: {wayback_url}", UserWarning)
            return None

        return etree_parse(  # nosec: B320
            source=text_file,
            parser=parser,
        )


_T = TypeVar("_T")


def safe_xpath(
    tree: _ElementTree | _Element,
    xpath: str,
    item_type: Type[_T],
) -> list[_T]:
    results = tree.xpath(xpath, smart_strings=False)
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
