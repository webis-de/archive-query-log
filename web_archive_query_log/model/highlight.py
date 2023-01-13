from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from typing import List, Union, Optional

from web_archive_query_log import LOGGER


class Highlight(str):
    pass


@dataclass(frozen=True, unsafe_hash=True)
class HighlightedText(str):
    """
    Highlighted text with ``<em>`` tags around the highlighted parts.
    Other tags are not supported.
    """
    html: str

    @property
    def text(self):
        return "".join(self.sequence)

    def __str__(self) -> str:
        return self.text

    @cached_property
    def sequence(self) -> List[Union[str, Highlight]]:
        parser = _HighlightParser()
        parser.feed(self.html)
        sequence = parser.sequence
        parser.close()
        return sequence


class _HighlightParser(HTMLParser):
    _current_sequence: List[Union[str, Highlight]]
    _current_data: Optional[str]
    _current_is_highlight: bool

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._current_sequence = []
        self._current_data = None
        self._current_is_highlight = False

    @property
    def sequence(self) -> List[Union[str, Highlight]]:
        sequence = self._current_sequence
        if self._current_data is not None:
            sequence.append(self._current_data)
        return sequence

    def handle_starttag(self, tag: str, attrs):
        if tag != "em":
            raise SyntaxError("Can only parse <em> tags.")
        if attrs:
            raise SyntaxError("Cannot parse attributes.")
        if self._current_is_highlight:
            raise SyntaxError("Nested <em> tags are not supported.")
        if self._current_data is not None:
            self._current_sequence.append(self._current_data)
        else:
            LOGGER.debug("Empty non-hightlight string.")
        self._current_data = None
        self._current_is_highlight = True

    # Overridable -- handle end tag
    def handle_endtag(self, tag: str):
        if tag != "em":
            raise SyntaxError("Can only parse <em> tags.")
        if not self._current_is_highlight:
            raise SyntaxError("Nested <em> tags are not supported.")
        if self._current_data is not None:
            self._current_sequence.append(Highlight(self._current_data))
        else:
            LOGGER.debug("Empty highlight string.")
        self._current_data = None
        self._current_is_highlight = False

    def handle_charref(self, name: str):
        raise AssertionError(
            "Should never be called because convert_charrefs is True."
        )

    def handle_entityref(self, name: str):
        raise AssertionError(
            "Should never be called because convert_charrefs is True."
        )

    def handle_data(self, data: str):
        self._current_data = data

    def handle_comment(self, data: str):
        raise SyntaxError("Comments are not supported.")

    def handle_decl(self, decl: str):
        raise SyntaxError("Doctype declarations are not supported.")

    def handle_pi(self, data: str):
        raise SyntaxError("Processing instructions are not supported.")
