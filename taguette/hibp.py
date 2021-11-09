import hashlib
from tornado.httpclient import AsyncHTTPClient

from .utils import _f
from .validate import InvalidFormat


SHA1_HEXDIGEST_LEN = 40
HIBP_PREFIX_LEN = 5


_http_client = AsyncHTTPClient()


async def check_password(base_url, password):
    sha1 = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    response = await _http_client.fetch(
        base_url.rstrip('/') + '/range/' + sha1[:HIBP_PREFIX_LEN],
        headers={'User-Agent': 'taguette'},
    )
    hits = response.body.decode('ascii').splitlines()
    for hit in hits:
        digest = hit[:SHA1_HEXDIGEST_LEN - HIBP_PREFIX_LEN].upper()
        if digest == sha1[HIBP_PREFIX_LEN:]:
            raise InvalidFormat(_f("This password has been exposed in data "
                                   "breaches and is not secure"))
