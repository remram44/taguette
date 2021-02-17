import asyncio

from .typesense import TypeSenseIndexer


__all__ = ['get_indexer']


def get_indexer(data):
    indexer = TypeSenseIndexer(data)
    asyncio.get_event_loop().run_until_complete(indexer.start())
    return indexer
