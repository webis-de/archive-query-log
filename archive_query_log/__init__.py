from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("archive-query-log")
except PackageNotFoundError:
    __version__ = "unknown"
