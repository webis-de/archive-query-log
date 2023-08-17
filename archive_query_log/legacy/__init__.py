from logging import getLogger
from pathlib import Path

PROJECT_DIRECTORY_PATH = Path(__file__).parent.parent.parent
DATA_DIRECTORY_PATH = PROJECT_DIRECTORY_PATH / "data"

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

LOGGER = getLogger(__name__)

if __name__ == "__main__":
    from archive_query_log.legacy.cli import main

    main()
