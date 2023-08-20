from logging import getLogger, Logger
from pathlib import Path

PROJECT_DIRECTORY_PATH: Path = Path(__file__).parent.parent.parent
DATA_DIRECTORY_PATH: Path = PROJECT_DIRECTORY_PATH / "data"

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

LOGGER: Logger = getLogger(__name__)

if __name__ == "__main__":
    from archive_query_log.legacy.cli import main

    main()
