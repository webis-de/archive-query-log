from click import Parameter, Context


def validate_domain(
        _context: Context,
        _parameter: Parameter,
        value: str,
) -> str:
    if not value.islower():
        raise ValueError("Domain must be lowercase.")
    if "." not in value:
        raise ValueError("Not a valid domain.")
    return value
