from warc_cache import WarcCacheStore
from warcio.archiveiterator import ArchiveIterator



def process_unready_warc_files(warc_cache_store: WarcCacheStore) -> None:
    cache_dir = warc_cache_store.cache_dir_path
    unready_files = sorted(cache_dir.glob(".*"))

    for file_path in unready_files:
        try:
            with open(file_path, 'rb') as stream:
                parsed = list(ArchiveIterator(stream))
            if not parsed:
                continue

            ready_path = cache_dir / file_path.name[1:]  # remove leading dot
            file_path.rename(ready_path)
        except Exception as e:
            print(f"Failed to parse {file_path.name}: {e}")