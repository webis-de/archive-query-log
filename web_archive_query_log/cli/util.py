from urllib.parse import urlparse

from click.types import StringParamType, Path


class UrlParamType(StringParamType):
    name = "url"

    def convert(self, value, param, ctx):
        value = super().convert(value, param, ctx)
        if value is None:
            return None
        tokens = urlparse(value)
        if not tokens.scheme or not tokens.netloc:
            self.fail(f"{value} is not a valid URL", param, ctx)
        return value


URL = UrlParamType()

PathParam = Path
