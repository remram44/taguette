import asyncio
import atexit
import json
import logging
import os
import pkg_resources
import random
import subprocess
from tornado.httpclient import AsyncHTTPClient, HTTPClientError
import urllib.parse
import uuid


logger = logging.getLogger(__name__)


TERM_TIMEOUT = 30
KILL_TIMEOUT = 10


class TypeSenseIndexer(object):
    def __init__(self, data):
        self._http_client = AsyncHTTPClient()
        self.process = None
        self.data = data

        self.port = random.randint(30000, 65534)
        self.api_key = str(uuid.uuid4())

        atexit.register(self.close)

    async def start(self):
        if self.process is not None:
            raise ValueError("TypeSense server is already running")

        create = not os.path.exists(self.data)
        if create:
            os.mkdir(self.data)
        try:
            exe = pkg_resources.resource_filename(
                'taguette',
                'typesense-server.exe',
            )
            await self._start(exe)
        except (FileNotFoundError, OSError):
            await self._start('typesense-server.exe')

        if create:
            await self._api_call(
                '/collections',
                {
                    'name': 'all_documents',
                    'fields': [
                        {'name': 'priority', 'type': 'int32'},
                        {'name': 'project_id', 'type': 'int32'},
                        {'name': 'name', 'type': 'string'},
                        {'name': 'description', 'type': 'string'},
                        {'name': 'body', 'type': 'string'},
                    ],
                    'default_sorting_field': 'priority',
                },
            )

    async def _start(self, exe):
        self.process = subprocess.Popen(
            [
                exe,
                '-d',
                self.data,
                '-a',
                self.api_key,
                '--api-address',
                '127.0.0.1',
                '--api-port',
                str(self.port),
                '--peering-port',
                str(self.port + 1),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Started TypeSense, pid %d", self.process.pid)

        # Wait for it to come up (= not return 503)
        for _ in range(60):
            await asyncio.sleep(2)
            try:
                await self._api_call('/')
            except HTTPClientError as e:
                if e.code == 503:
                    continue  # Not ready
                elif e.code < 500:
                    logger.info("TypeSense is ready")
                    return
                else:
                    raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        if self.process is not None:
            logger.info("Stopping TypeSense")
            self.process.terminate()
            self.process.wait(TERM_TIMEOUT)
            if self.process.returncode is None:
                self.process.kill()
                self.process.wait(KILL_TIMEOUT)
                if self.process.returncode is None:
                    print(
                        "Couldn't stop TypeSense process {0}!".format(
                            self.process.pid,
                        )
                    )
            self.process = None

    async def _api_call(self, uri, json_body=None, method=None):
        url = 'http://127.0.0.1:{0}{1}'.format(self.port, uri)
        kwargs = dict(
            headers={'X-TypeSense-Api-Key': self.api_key},
        )
        if json_body:
            kwargs['method'] = 'POST'
            kwargs['body'] = json.dumps(json_body)
        if method is not None:
            kwargs['method'] = method
        response = None
        for _ in range(20):
            try:
                response = await self._http_client.fetch(url, **kwargs)
                break
            except HTTPClientError as e:
                if e.code == 503:
                    # Not ready
                    logger.info("TypeSense is not ready, retrying...")
                    await asyncio.sleep(2)
                else:
                    raise
        if response is None:
            response = await self._http_client.fetch(url, **kwargs)
        return json.loads(response.body.decode('utf-8'))

    async def add_project(self, project_id):
        # Nothing to do
        pass

    async def remove_project(self, project_id):
        await self._api_call(
            '/collections/all_documents/documents?'
            + urllib.parse.urlencode({
                'filter_by': 'project_id:={0}'.format(project_id),
            }),
            method='DELETE',
        )

    async def add_document(self, project_id, id, name, description, body):
        args = (
            '/collections/all_documents/documents',
            {
                'id': str(id),
                'project_id': project_id,
                'priority': 100,
                'name': name,
                'description': description,
                'body': body,
            },
        )

        try:
            await self._api_call(*args)
        except HTTPClientError as e:
            if e.code == 409:  # Conflict
                await self.remove_document(project_id, id)
                await self._api_call(*args)
            else:
                raise

    async def update_document(self, project_id, id, name, description):
        await self._api_call(
            '/collections/all_documents/documents/{id}'.format(id=id),
            {
                'name': name,
                'description': description,
            },
            method='PATCH',
        )

    async def remove_document(self, project_id, document_id):
        await self._api_call(
            '/collections/all_documents/documents/{0}'.format(document_id),
            method='DELETE'
        )

    async def search(self, project_id, text):
        return await self._api_call(
            '/collections/all_documents/documents/search?'
            + urllib.parse.urlencode({
                'filter_by': 'project_id:={0}'.format(project_id),
                'q': text,
                'query_by': 'name,description,body',
            }),
        )
