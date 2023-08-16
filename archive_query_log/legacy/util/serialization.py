from marshmallow.fields import Field

from archive_query_log.legacy.model import HighlightedText


class HighlightedTextField(Field):
    """
    Field that serializes to an HTML string and deserializes
    to a highlighted text.
    """

    def _serialize(self, value: HighlightedText, attr, obj, **kwargs):
        if value is None:
            return None
        return value.html

    def _deserialize(self, value: str, attr, data, **kwargs):
        if value is None:
            return None
        return HighlightedText(value)
