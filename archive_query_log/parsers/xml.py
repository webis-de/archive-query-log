from typing import Literal, Type, TypeVar, Iterable
from warnings import warn

from cssselect import GenericTranslator
from cssselect.parser import parse as cssselect_parse
from lxml.etree import parse as etree_parse, XMLParser, HTMLParser  # nosec: B410
# noinspection PyProtectedMember
from lxml.etree import _ElementTree, _Element  # nosec: B410
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
    return etree_parse(  # nosec: B320
        source=record.content_stream(),
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
            f"must be of type {item_type}, found: {types}")
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
        raise ValueError(
            "An attribute and text=True are not allowed at the same time.")
    if text:
        return f"{xpath}//text()"
    else:
        return f"{xpath}/@{attribute}"
