from hashlib import blake2b
from re import Pattern
from warnings import warn


def content_digest(content: str) -> str:
    """
    Stable hash of parsed content, used as a component of derived document IDs.
    Must not use the builtin `hash()`, as that is salted per interpreter and
    would make the derived IDs differ between runs.
    """
    return blake2b(content.encode("utf-8"), digest_size=16).hexdigest()


def clean_text(
        text: str,
        remove_pattern: Pattern | None,
        space_pattern: Pattern | None,
) -> str | None:
    # Null characters are rejected by Elasticsearch completion fields.
    text = text.replace("\x00", "")
    # Remove any provider-specific patterns.
    if remove_pattern is not None:
        text = remove_pattern.sub("", text)
    # Replace any provider-specific space-indicating characters.
    if space_pattern is not None:
        text = space_pattern.sub(" ", text)
    # Clear surrounding whitespace.
    text = text.strip()
    # Normalize whitespace delimiters.
    text = " ".join(text.split())
    if text == "":
        return None
    return text


def clean_int(
        text: str,
        remove_pattern: Pattern | None,
) -> int | None:
    if remove_pattern is not None:
        text = remove_pattern.sub("", text)
    text = text.strip()
    try:
        parsed = int(text)
    except ValueError:
        warn(RuntimeWarning(f"Could not parse int: {text}"))
        return None
    return parsed
