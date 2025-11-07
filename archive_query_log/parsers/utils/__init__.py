from re import Pattern
from warnings import warn


def clean_text(
        text: str,
        remove_pattern: Pattern | None,
        space_pattern: Pattern | None,
) -> str | None:
    if remove_pattern is not None:
        text = remove_pattern.sub("", text)
    if space_pattern is not None:
        text = space_pattern.sub(" ", text)
    text = text.strip()
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
