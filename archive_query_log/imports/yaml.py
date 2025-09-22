from pathlib import Path
from typing import MutableMapping
from typing import Sequence, Iterable

from diskcache import Index
from tqdm.auto import tqdm
from whois import whois
from whois.parser import PywhoisError
from yaml import safe_load

from archive_query_log.config import Config
from archive_query_log.providers import add_provider


def _provider_name(
    i: int,
    main_domain: str,
    provider_names: MutableMapping[str, str],
    review: bool,
) -> str | None:
    provider_name_suggest: str | None
    if main_domain in provider_names:
        if not review:
            return provider_names[main_domain]
        else:
            provider_name_suggest = provider_names[main_domain].strip()
    else:
        try:
            main_domain_info = whois(main_domain)
        except PywhoisError:
            main_domain_info = None
        if main_domain_info is not None:
            main_org: str | list[str] | None = main_domain_info.org
            if isinstance(main_org, list):
                main_org = main_org[0]
            if main_org is not None:
                for restricted_phrase in [
                    "redacted",
                    "privacy",
                    "domain protection",
                    "not disclosed",
                    "identity protection",
                    "domains by proxy",
                ]:
                    if restricted_phrase in main_org.casefold():
                        main_org = None
                        break
            if main_org is not None:
                for suffix in [
                    "Inc",
                    "LLC",
                    "Ltd",
                    "LTD",
                    "GmbH",
                    "AG",
                    "S.A",
                    "SE",
                    "Co",
                    "Pty",
                    "B.V",
                    "S.L",
                    "S.R.L",
                    "S.A.S",
                    "SAS",
                    "AB",
                    "&",
                ]:
                    main_org = main_org.removesuffix(f", {suffix}.")
                    main_org = main_org.removesuffix(f", {suffix}")
                    main_org = main_org.removesuffix(f" {suffix}.")
                    main_org = main_org.removesuffix(f" {suffix}")
                provider_name_suggest = main_org.strip()
            else:
                provider_name_suggest = None
        else:
            provider_name_suggest = None
    provider_name = input(
        f"Please enter search provider #{i} name (https://{main_domain}) "
    ).strip()
    if provider_name == "" and provider_name_suggest is not None:
        provider_name = provider_name_suggest
    if provider_name == "":
        return None
    provider_names[main_domain] = provider_name
    return provider_name


def import_providers(
    config: Config,
    services_path: Path,
    cache_path: Path,
    review: int | None,
    no_merge: bool,
    auto_merge: bool,
    dry_run: bool = False,
) -> None:
    print("Load providers from services file.")
    with services_path.open("r") as file:
        services_list: Sequence[dict] = safe_load(file)
    print(f"Found {len(services_list)} service definitions.")

    services: Iterable[dict] = services_list
    provider_names: MutableMapping[str, str] = Index(str(cache_path))

    if auto_merge or no_merge:
        services = tqdm(
            services,
            desc="Import providers",
            unit="provider",
        )

    num_services = len(services_list)

    ask_for_name = True
    service: dict
    for i, service in enumerate(services):
        if "domains" not in service:
            raise ValueError(
                f"Service definition #{i} from {services_path} "
                f"has no domains: {service}"
            )

        if "query_parsers" not in service or len(service["query_parsers"]) == 0:
            continue

        main_domain = service["domains"][0]
        if ask_for_name:
            name = _provider_name(
                i, main_domain, provider_names, review is not None and review <= i
            )
            if name is None:
                ask_for_name = False
        else:
            name = None

        add_provider(
            config=config,
            name=name,
            description=None,
            notes=service.get("notes"),
            exclusion_reason=service.get("excluded"),
            domains=set(service["domains"]),
            url_path_prefixes=set(service["focused_url_prefixes"]),
            priority=num_services - i,
            no_merge=no_merge,
            auto_merge=auto_merge,
            dry_run=dry_run,
        )
