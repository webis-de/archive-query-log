from typing import Literal
from warnings import warn

from cssselect import GenericTranslator
from cssselect.parser import parse as cssselect_parse
# pylint: disable=no-name-in-module
from lxml.etree import parse as etree_parse, XMLParser, HTMLParser
# noinspection PyProtectedMember
# pylint: disable=no-name-in-module
from lxml.etree import _ElementTree
from warcio.recordloader import ArcWarcRecord

XmlParserType = Literal[
    "xml",
    "html",
]


def parse_xml_tree(record: ArcWarcRecord) -> _ElementTree | None:
    mime_type: str | None = record.http_headers.get_header("Content-Type")
    if mime_type is None:
        warn(UserWarning("No MIME type given."))
        return None
    mime_type = mime_type.split(";", maxsplit=1)[0]
    parser: XMLParser | HTMLParser
    if mime_type == "text/xml":
        parser = XMLParser()
    elif mime_type == "text/html":
        parser = HTMLParser()
    else:
        warn(UserWarning(f"Cannot find XML parser for MIME type: {mime_type}"))
        return None
    return etree_parse(
        source=record.content_stream(),
        parser=parser,
    )


def get_xml_xpath_non_empty_string(
        tree: _ElementTree,
        xpath: str,
) -> str | None:
    results = tree.xpath(xpath, smart_strings=False)
    if not isinstance(results, list):
        raise ValueError(
            f"XPath {xpath} did not return a list, was: {type(results)}")
    if not all(isinstance(result, str) for result in results):
        types = ", ".join(str(type(result)) for result in results)
        raise ValueError(
            f"XPath {xpath} did not return a list of strings, found: {types}")
    results = (result.strip() for result in results)
    results = (result for result in results if result != "")
    results = list(set(results))
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


_translator = GenericTranslator()


def text_xpath_from_css_selector(
        css_selector: str,
        attribute: str | None = None,
        text: bool = False,
) -> str:
    if attribute is None and not text:
        raise ValueError("Either an attribute or text=True must be given.")
    if attribute is not None and text:
        raise ValueError(
            "An attribute and text=True are not allowed at the same time.")

    selectors = cssselect_parse(css_selector)

    xpaths = (
        "//" + _translator.selector_to_xpath(
            selector,
            prefix="",
            translate_pseudo_elements=True,
        ).replace(
            "/descendant-or-self::*/", "//")
        for selector in selectors
    )

    if text:
        xpaths = (f"{xpath}//text()" for xpath in xpaths)
    else:
        xpaths = (f"{xpath}/@{attribute}" for xpath in xpaths)

    xpath = " | ".join(xpaths)
    return xpath
