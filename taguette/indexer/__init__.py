import asyncio

from .typesense import TypeSenseIndexer


__all__ = ['get_indexer']


class NullIndexer(object):
    def close(self):
        pass

    async def add_project(self, project_id):
        pass

    async def remove_project(self, project_id):
        pass

    async def add_document(self, project_id, id, name, description, body):
        pass

    async def update_document(self, project_id, id, name, description):
        pass

    async def remove_document(self, project_id, document_id):
        pass

    async def search(self, project_id, text):
        return []


def get_indexer(data):
    if data is not None:
        indexer = TypeSenseIndexer(data)
        asyncio.get_event_loop().run_until_complete(indexer.start())
    else:
        indexer = NullIndexer()
    return indexer
