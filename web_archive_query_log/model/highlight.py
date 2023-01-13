from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from typing import List, Union, Optional


class Highlight(str):
    depth: int

    def __new__(cls, value: str, depth: int):
        result = super().__new__(cls, value)
        result.depth = depth
        return result


@dataclass(frozen=True, unsafe_hash=True)
class HighlightedText(str):
    """
    Text with highlighting using``<em>`` tags.
    Other tags are not allowed.
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
    _sequence: List[Union[str, Highlight]]
    _data: Optional[str]
    _highlight_depth: int

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._sequence = []
        self._data = None
        self._highlight_depth = 0

    def _flush_data(self):
        if self._data is not None:
            if self._highlight_depth > 0:
                self._sequence.append(
                    Highlight(
                        self._data,
                        depth=self._highlight_depth
                    )
                )
            else:
                self._sequence.append(self._data)
        self._data = None

    @property
    def sequence(self) -> List[Union[str, Highlight]]:
        self._flush_data()
        return self._sequence

    def handle_starttag(self, tag: str, attrs):
        if tag != "em":
            raise SyntaxError("Can only parse <em> tags.")
        if attrs:
            raise SyntaxError("Cannot parse attributes.")
        self._flush_data()
        self._highlight_depth += 1

    # Overridable -- handle end tag
    def handle_endtag(self, tag: str):
        if tag != "em":
            raise SyntaxError("Can only parse <em> tags.")
        self._flush_data()
        self._highlight_depth -= 1

    def handle_charref(self, name: str):
        raise AssertionError(
            "Should never be called because convert_charrefs is True."
        )

    def handle_entityref(self, name: str):
        raise AssertionError(
            "Should never be called because convert_charrefs is True."
        )

    def handle_data(self, data: str):
        if self._data is None:
            self._data = data
        else:
            self._data += data

    def handle_comment(self, data: str):
        raise SyntaxError("Comments are not supported.")

    def handle_decl(self, decl: str):
        raise SyntaxError("Doctype declarations are not supported.")

    def handle_pi(self, data: str):
        raise SyntaxError("Processing instructions are not supported.")
