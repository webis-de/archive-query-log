from typing import Literal

from lxml.etree import parse, XMLParser, HTMLParser, _ElementTree
from warcio.recordloader import ArcWarcRecord

XmlParserType = Literal[
    "xml",
    "html",
]


def parse_xml_tree(record: ArcWarcRecord) -> _ElementTree:
    mime_type = record.http_headers.get_header("Content-Type")
    if mime_type is None:
        raise ValueError("No MIME type given.")
    elif mime_type == "text/xml":
        parser = XMLParser()
    elif mime_type == "text/html":
        parser = HTMLParser()
    else:
        raise ValueError(f"Cannot find XML parser for MIME type: {mime_type}")
    return parse(
        source=record.content_stream(),
        parser=parser,
    )


def get_xml_xpath_string(tree: _ElementTree, xpath: str) -> str:
    result = tree.xpath(xpath)
    if isinstance(result, str):
        return result
    else:
        raise ValueError(f"XPath {xpath} did not return a string.")
