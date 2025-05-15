from typing import Dict, Any, List
from urllib.parse import urlparse

from click import Parameter, Context
from click.shell_completion import CompletionItem
from click.types import StringParamType, Path, Choice


class UrlParam(StringParamType):
    name = "url"

    def convert(self, value, param, ctx):
        value = super().convert(value, param, ctx)
        if value is None:
            return None
        tokens = urlparse(value)
        if not tokens.scheme or not tokens.netloc:
            self.fail(f"{value} is not a valid URL", param, ctx)
        return value


URL = UrlParam()

PathParam = Path


class ServiceChoice(Choice):

    def __init__(self) -> None:
        super().__init__(choices=[], case_sensitive=False)

    def _ensure_choices(self):
        if len(self.choices) == 0:
            from archive_query_log.legacy.config import SERVICES
            self.choices = sorted(SERVICES.keys())

    def to_info_dict(self) -> Dict[str, Any]:
        self._ensure_choices()
        return super().to_info_dict()

    def get_metavar(self, param: Parameter, ctx: Context) -> str | None:
        self._ensure_choices()
        return super().get_metavar(param, ctx)

    def get_missing_message(self, param: Parameter, ctx: Context | None) -> str:
        self._ensure_choices()
        return super().get_missing_message(param, ctx)

    def convert(
            self,
            value: Any,
            param: Parameter | None,
            ctx: Context | None,
    ) -> Any:
        self._ensure_choices()
        return super().convert(value, param, ctx)

    def __repr__(self) -> str:
        self._ensure_choices()
        return super().__repr__()

    def shell_complete(
            self,
            ctx: Context,
            param: Parameter,
            incomplete: str,
    ) -> List[CompletionItem]:
        self._ensure_choices()
        return super().shell_complete(ctx, param, incomplete)
