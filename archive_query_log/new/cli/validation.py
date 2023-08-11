from typing import Sequence

from click import Parameter, Context, BadParameter


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


def validate_split_domains(
        _context: Context,
        _parameter: Parameter,
        value: Sequence[str],
) -> Sequence[str]:
    valid_domains = []
    for domains in value:
        for domain in domains.split(","):
            domain = domain.strip()
            if not domain.islower():
                raise BadParameter(f"Domain must be lowercase: {domain}")
            if "." not in domain:
                raise BadParameter(f"Not a valid domain: {domain}")
            valid_domains.append(domain)
    return valid_domains
