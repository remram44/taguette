from .typesense import TypeSenseIndexer


__all__ = ['get_indexer']


async def get_indexer(data):
    indexer = TypeSenseIndexer(data)
    await indexer.start()
    return indexer
