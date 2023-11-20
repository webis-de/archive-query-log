from typing import Literal
from warnings import warn

from lxml.etree import parse, XMLParser, HTMLParser
# noinspection PyProtectedMember
from lxml.etree import _ElementTree
from warcio.recordloader import ArcWarcRecord

XmlParserType = Literal[
    "xml",
    "html",
]


def parse_xml_tree(record: ArcWarcRecord) -> _ElementTree:
    mime_type: str | None = record.http_headers.get_header("Content-Type")
    if mime_type is None:
        raise ValueError("No MIME type given.")
    mime_type = mime_type.split(";", maxsplit=1)[0]
    if mime_type == "text/xml":
        parser = XMLParser()
    elif mime_type == "text/html":
        parser = HTMLParser()
    else:
        raise ValueError(f"Cannot find XML parser for MIME type: {mime_type}")
    return parse(
        source=record.content_stream(),
        parser=parser,
    )


def get_xml_xpath_string(tree: _ElementTree, xpath: str) -> str | None:
    results = tree.xpath(xpath, smart_strings=False)
    if not isinstance(results, list):
        raise ValueError(
            f"XPath {xpath} did not return a list, was: {type(results)}")
    if len(results) == 0:
        return None
    if len(results) > 1:
        warn(RuntimeWarning(
            f"XPath {xpath} returned more than one result: {results}"))
    result = results[0]
    if isinstance(result, str):
        return result
    else:
        raise ValueError(
            f"XPath {xpath} did not return a string, was: {type(result)}")
