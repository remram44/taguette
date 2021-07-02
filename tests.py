import aiohttp
import asyncio
from datetime import datetime
import functools
import itertools
import json
import os
import random
import re
import sqlalchemy
from sqlalchemy.orm import close_all_sessions
import string
import tempfile
import textwrap
import time
from tornado.testing import AsyncTestCase, gen_test, AsyncHTTPTestCase
import unittest
from unittest import mock
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree

from taguette import __version__
from taguette import convert, database, extract, main, validate, web


if 'TAGUETTE_TEST_DB' in os.environ:
    DATABASE_URI = os.environ['TAGUETTE_TEST_DB']
else:
    DATABASE_URI = 'sqlite://'


def _compare_xml(e1, e2):
    assert e1.tag == e2.tag
    assert e1.attrib == e2.attrib
    for c1, c2 in itertools.zip_longest(e1, e2):
        assert c1 is not None and c2 is not None
        _compare_xml(c1, c2)


def compare_xml(str1, str2):
    et1 = ElementTree.fromstring(str1)
    et2 = ElementTree.fromstring(str2)
    _compare_xml(et1, et2)


def with_tempdir(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            return func(*args, **kwargs, tmp=tmp)

    return wrapper


class TestConvert(AsyncTestCase):
    config = dict(
        CONVERT_TO_HTML_TIMEOUT=60,
    )

    @gen_test
    async def test_convert_html(self):
        """Tests converting HTML, using BeautifulSoup and Bleach"""
        body = (
            b"<!DOCTYPE html>\n"
            b"<html>\n  <head>\n  <title>Test</title>\n</head>\n<body>"
            b"<h1>Example</h1><p>This is an <a>example</a> text document.\n"
            b"It should be <blink>converted</blink>.</p>\n\n"
            b"<p>It has another paragraph <strong>here</strong>, "
            b"images: <img width=\"50\" src=\"here.png\"> "
            b"<img title=\"important\" src=\"/over/there.png\" width=\"30\"> "
            b"<img src=\"http://and/the/last/one.png\" class=\"a\">, and "
            b"links: <a href=\"here\">1</a> "
            b"<a title=\"important\" href=\"/over/there\">2</a> "
            b"<a href=\"http://and/the/last/one\" class=\"a\">3</a></p>\n"
            b"</body></html>\n"
        )
        with mock.patch('tornado.process.Subprocess', object()):
            body = await convert.to_html(body, 'text/html', 'test.html',
                                         self.config)
        self.assertEqual(
            body,
            "<h1>Example</h1><p>This is an example text document.\n"
            "It should be converted.</p>\n\n"
            "<p>It has another paragraph <strong>here</strong>, "
            "images: <img src=\"/static/missing.png\"> "
            "<img src=\"/static/missing.png\"> "
            "<img src=\"/static/missing.png\">, and "
            "links: <a title=\"here\">1</a> "
            "<a title=\"/over/there\">2</a> "
            "<a href=\"http://and/the/last/one\">3</a></p>"
        )

    def test_filename(self):
        validate.filename.windows = True  # escape device names

        self.assertEqual(validate.filename('/etc/passwd'), 'passwd')
        self.assertEqual(validate.filename('/etc/passwd.txt'), 'passwd.txt')
        self.assertEqual(validate.filename('ééé'), '_')
        self.assertEqual(validate.filename('ééé.pdf'), '_.pdf')
        self.assertEqual(validate.filename('/tmp/NUL.pdf'), '_NUL.pdf')
        self.assertEqual(validate.filename('/tmp/nul.pdf'), '_nul.pdf')


class TestPassword(unittest.TestCase):
    @staticmethod
    def random_password():
        alphabet = (
            string.ascii_letters + string.digits +
            string.punctuation + string.whitespace
        )
        password = [random.choice(alphabet) for _ in range(4, 16)]
        return ''.join(password)

    def test_bcrypt(self):
        for _ in range(3):
            password = self.random_password()
            user = database.User(login='user')
            user.set_password(password, 'bcrypt')
            self.assertTrue(user.hashed_password.startswith('bcrypt:'))
            print(user.hashed_password)

            self.assertTrue(user.check_password(password))
            self.assertFalse(user.check_password(password[:-1]))

    def test_pbkdf2(self):
        for _ in range(3):
            password = self.random_password()
            user = database.User(login='user')
            user.set_password(password)
            self.assertTrue(user.hashed_password.startswith('pbkdf2:'))
            print(user.hashed_password)

            self.assertTrue(user.check_password(password))
            self.assertFalse(user.check_password(password[:-1]))


class TestMeasure(unittest.TestCase):
    def test_extract_highlight(self):
        """Tests extracting a highlight from an HTML document."""
        html = '<p><u>H\xE9llo</u> R\xE9mi <i>what is</i> up ?</p>'
        snippet = extract.extract(html, 7, 15)
        self.assertEqual(snippet,
                         '<p>R\xE9mi <i>wh</i></p>')
        snippet = extract.extract(html, 1, 5)
        self.assertEqual(snippet,
                         '<p><u>\xE9ll</u></p>')
        snippet = extract.extract(html, 7, 12)
        self.assertEqual(snippet,
                         '<p>R\xE9mi</p>')

    def test_highlight(self):
        """Tests highlighting an HTML document with only ASCII characters."""
        html = '<p><u>Hello</u> there <i>World</i></p>'
        highlights = [
            (0, 1, ['tag1']), (2, 3, []),
            (4, 8, ['tag1', 'tag2']), (10, 14, ['tag2']), (15, 17, ['tag1']),
        ]
        self.assertEqual(
            extract.highlight(html, highlights)
            .replace('<span class="highlight">', '{')
            .replace('</span>', '}'),
            '<p><u>{H}e{l}l{o}</u>{ th}er{e }<i>{Wo}r{ld}</i></p>',
        )

        self.assertEqual(
            extract.highlight(html, highlights, show_tags=True)
            .replace('<span class="taglist"> [', '[')
            .replace(']</span>', ']')
            .replace('<span class="highlight">', '{')
            .replace('</span>', '}'),
            '<p><u>{H}[tag1]e{l}[]l{o}</u>{ th}[tag1, tag2]er{e }' +
            '<i>{Wo}[tag2]r{ld}[tag1]</i></p>',
        )

    def test_highlight_unicode(self):
        """Tests highlighting an HTML document with unicode characters."""
        html = '<p><u>H\xE9ll\xF6</u> the\xAEe <i>\u1E84o\xAEld</i>!</p>'
        highlights = [
            (0, 1, ['tag1']), (3, 4, []),
            (6, 10, ['tag1', 'tag2']), (13, 19, ['tag2']), (21, 23, ['tag1']),
        ]
        self.assertEqual(
            extract.highlight(html, highlights)
            .replace('<span class="highlight">', '{')
            .replace('</span>', '}'),
            '<p><u>{H}\xE9{l}l{\xF6}</u>{ th}e\xAE'
            '{e }<i>{\u1E84o}\xAE{ld}</i>!</p>',
        )

        self.assertEqual(
            extract.highlight(html, highlights, show_tags=True)
            .replace('<span class="taglist"> [', '[')
            .replace(']</span>', ']')
            .replace('<span class="highlight">', '{')
            .replace('</span>', '}'),
            '<p><u>{H}[tag1]\xE9{l}[]l{\xF6}</u>{ th}[tag1, tag2]e\xAE'
            '{e }<i>{\u1E84o}[tag2]\xAE{ld}[tag1]</i>!</p>',
        )

    def test_highlight_nested(self):
        """Test highlighting an HTML document when highlights are nested."""
        html = '<p><u>Hello</u> there <i>World</i></p>'

        # Do all the combinations of nesting orders
        starts = [0, 3, 10]
        for ends in itertools.permutations([14, 15, 17]):
            highlights = [
                (starts[0], ends[0], ['tag1']), (starts[1], ends[1], []),
                (starts[2], ends[2], ['tag1', 'tag2']),
            ]

            self.assertEqual(
                extract.highlight(html, highlights)
                .replace('<span class="highlight">', '{')
                .replace('</span>', '}'),
                '<p><u>{Hello}</u>{ there }<i>{World}</i></p>',
            )

            expected = {
                (14, 15, 17): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[tag1]{r}[]{ld}[tag1, tag2]</i></p>',
                (14, 17, 15): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[tag1]{r}[tag1, tag2]{ld}[]</i></p>',
                (15, 14, 17): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[]{r}[tag1]{ld}[tag1, tag2]</i></p>',
                (15, 17, 14): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[tag1, tag2]{r}[tag1]{ld}[]</i></p>',
                (17, 14, 15): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[]{r}[tag1, tag2]{ld}[tag1]</i></p>',
                (17, 15, 14): '<p><u>{Hello}</u>{ ther'
                              'e }<i>{Wo}[tag1, tag2]{r}[]{ld}[tag1]</i></p>',
            }[ends]
            self.assertEqual(
                extract.highlight(html, highlights, show_tags=True)
                .replace('<span class="taglist"> [', '[')
                .replace(']</span>', ']')
                .replace('<span class="highlight">', '{')
                .replace('</span>', '}'),
                expected,
                "ends=%r" % (ends,),
            )


class TestValidate(unittest.TestCase):
    def test_export_filename(self):
        self.assertEqual(
            web.export.safe_filename('**My sweet project / 2**'),
            'My sweet project  2',
        )
        self.assertEqual(
            web.export.safe_filename("Rémi's project"),
            "Rmis project",
        )


class MyHTTPTestCase(AsyncHTTPTestCase):
    xsrf = None

    def setUp(self):
        web.Application.check_messages = lambda *a: None
        validate.filename.windows = True  # escape device names
        super(MyHTTPTestCase, self).setUp()
        # Tornado's http client doesn't support cookies
        self.http_client = aiohttp.ClientSession(
            # Need to set 'unsafe' to work when host is an IP address
            cookie_jar=aiohttp.cookiejar.CookieJar(unsafe=True),
        )

    def tearDown(self):
        self.io_loop.run_sync(
            lambda: self.http_client.close(),
            timeout=3,
        )

    def _fetch(self, url, method='GET', **kwargs):
        # Copied from tornado.testing.AsyncHTTPTestCase.fetch()
        if not url.lower().startswith(('http://', 'https://')):
            url = self.get_url(url)
        return getattr(self.http_client, method.lower())(url, **kwargs)

    def aget(self, url):
        return self._fetch(url, allow_redirects=False)

    def apost(self, url, **kwargs):
        cookies = self.http_client.cookie_jar.filter_cookies(self.get_url('/'))
        if '_xsrf' in cookies:
            token = cookies['_xsrf'].value
            if 'data' in kwargs:
                if isinstance(kwargs['data'], dict):
                    kwargs['data'] = dict(kwargs['data'], _xsrf=token)
            elif 'json' in kwargs:
                url = '%s%s%s' % (url, '&' if '?' in url else '?',
                                  urlencode(dict(_xsrf=token)))
        if 'files' in kwargs:
            files = kwargs.pop('files')
            data = aiohttp.FormData()
            for key, value in kwargs.get('data', {}).items():
                data.add_field(key, value)
            for key, (filename, content_type, value) in files.items():
                data.add_field(
                    key, value,
                    content_type=content_type,
                    filename=filename,
                )
            kwargs['data'] = data
        return self._fetch(url, method='POST', allow_redirects=False, **kwargs)


def set_dumb_password(self, user):
    user.set_password('hackme')


class TestMultiuser(MyHTTPTestCase):
    def get_app(self):
        with mock.patch.object(web.Application, '_set_password',
                               new=set_dumb_password):
            self.application = web.make_app(dict(
                main.DEFAULT_CONFIG,
                NAME="Test Taguette instance", PORT=7465,
                DATABASE=DATABASE_URI,
                TOS_FILE=None,
                EMAIL='test@example.com',
                MAIL_SERVER={'host': 'localhost', 'port': 25},
                COOKIES_PROMPT=True,
                MULTIUSER=True,
                SECRET_KEY='2PbQ/5Rs005G/nTuWfibaZTUAo3Isng3QuRirmBK',
            ))
            return self.application

    def tearDown(self):
        super(TestMultiuser, self).tearDown()
        close_all_sessions()
        engine = sqlalchemy.create_engine(DATABASE_URI)
        database.Base.metadata.drop_all(bind=engine)

    @gen_test
    async def test_login(self):
        # Fetch index, should have welcome message and register link
        async with self.aget('/') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'>Welcome</h1>', await response.read())
            self.assertIn(b'Register now</a> for free and get started',
                          await response.read())

        # Only admin so far
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin'])

        # Fetch registration page, should hit cookies prompt
        async with self.aget('/register') as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'],
                             '/cookies?next=%2Fregister')

        # Accept cookies
        async with self.apost(
            '/cookies',
            data=dict(next='/register'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/register')

        # Fetch registration page
        async with self.aget('/register') as response:
            self.assertEqual(response.status, 200)

        # Register
        async with self.apost(
            '/register',
            data=dict(login='Tester',
                      password1='hacktoo', password2='hacktoo'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # User exists in database
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin', 'tester'])

        # Fetch index, should have project list
        async with self.aget('/') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'>Welcome tester</h1>', await response.read())
            self.assertIn(b'Here are your projects', await response.read())

        # Fetch project creation page
        async with self.aget('/project/new') as response:
            self.assertEqual(response.status, 200)

        # Create a project
        async with self.apost(
            '/project/new',
            data=dict(name='test project', description=''),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/project/1')

        # Log out
        async with self.aget('/logout') as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Hit error page
        async with self.aget('/api/project/1/highlights/') as response:
            self.assertEqual(response.status, 403)
            self.assertEqual(await response.json(), {"error": "Not logged in"})

        # Fetch login page
        async with self.aget(
            '/login?' + urlencode(dict(next='/project/1')),
        ) as response:
            self.assertEqual(response.status, 200)

        # Log in
        async with self.apost(
            '/login',
            data=dict(next='/project/1', login='admin', password='hackme'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/project/1')

        # Check redirect to account
        async with self.aget('/.well-known/change-password') as response:
            self.assertEqual(response.status, 301)
            self.assertEqual(response.headers['Location'], '/account')

    @gen_test(timeout=30)
    async def test_projects(self):
        # project 1               project 2
        # ---------               ---------
        # create
        # (tag 1 'interesting')
        #                         create
        #                         (tag 2 'interesting')
        #                         tag 3 'people'
        #                         tag 4 'interesting.places'
        # doc 1
        #                         doc 2
        # hl 1 doc=1 tags=[1]
        #                         change project metadata
        #                         doc 3
        #                         hl 2 doc=2 tags=[4]
        #                         hl 3 doc=2 tags=[2, 3]
        #                         hl 4 doc=3 tags=[3]
        #                         highlights 'people*': [3, 4]
        #                         highlights 'interesting.places*': [2]
        #                         highlights 'interesting*': [2, 3]
        #                         highlights: [2, 3, 4]
        #                         export doc 2
        #                         merge tag 3 -> 2
        #                         highlights: [2, 3, 4]

        # Accept cookies
        async with self.apost('/cookies', data=dict()) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Log in
        async with self.aget('/login') as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/login',
            data=dict(next='/', login='admin', password='hackme'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Create project 1
        async with self.aget('/project/new') as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/project/new',
            data=dict(
                name='\uFF9F\uFF65\u273F\u30FE\u2572\x28\uFF61\u25D5\u203F'
                     '\u25D5\uFF61\x29\u2571\u273F\uFF65\uFF9F',
                description="R\xE9mi's project",
            ),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/project/1')

        # Check project page
        async with self.aget('/project/1') as response:
            self.assertEqual(response.status, 200)
            body = await response.text()
        self.assertIn('we are good at engineering', body)
        idx = body.index('we are good at engineering')
        init_js = '\n'.join(body[idx:].splitlines()[1:10])
        self.assertEqual(
            init_js,
            '<script type="text/javascript">\n'
            '  var user_login = "admin";\n'
            '  var project_id = 1;\n'
            '  var last_event = -1;\n'
            '  var documents = {};\n'
            '  var highlights = {};\n'
            '  var tags = %s;\n'
            '  var members = {"admin": {"privileges": "ADMIN"}};\n'
            '</script>' % (
                json.dumps(
                    {
                        "1": {
                            "count": 0, "id": 1, "path": "interesting",
                            "description": "Further review required",
                        },
                    },
                    sort_keys=True),
            ),
        )

        # Start polling
        poll_proj1 = await self.poll_event(1, -1)

        # Create project 2
        async with self.aget('/project/new') as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/project/new',
            data=dict(name='other project', description=''),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/project/2')

        # Start polling
        poll_proj2 = await self.poll_event(2, -1)

        # Create tags in project 2
        async with self.apost(
            '/api/project/2/tag/new',
            json=dict(path='people', description="People of interest"),
        ) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(
            await poll_proj2,
            {'tag_add': [{'description': "People of interest", 'tag_id': 3,
                          'tag_path': 'people'}],
             'id': 1})
        poll_proj2 = await self.poll_event(2, 1)

        async with self.apost(
            '/api/project/2/tag/new',
            json=dict(path='interesting.places', description=''),
        ) as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(
            await poll_proj2,
            {'tag_add': [{'description': '', 'tag_id': 4,
                          'tag_path': 'interesting.places'}],
             'id': 2})
        poll_proj2 = await self.poll_event(2, 2)

        # Create document 1 in project 1
        name = '\u03A9\u2248\xE7\u221A\u222B\u02DC\xB5\u2264\u2265\xF7'
        async with self.apost(
            '/api/project/1/document/new',
            data=dict(name=name, description=''),
            files=dict(file=('../NUL.html', 'text/plain', b'content here')),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"created": 1})
        db = self.application.DBSession()
        doc = db.query(database.Document).get(1)
        self.assertEqual(doc.name, name)
        self.assertEqual(doc.description, '')
        self.assertEqual(doc.filename, '_NUL.html')
        self.assertEqual(
            await poll_proj1,
            {'document_add': [{'description': '', 'document_id': 1,
                               'document_name': name}], 'id': 3})
        poll_proj1 = await self.poll_event(1, 3)

        # Create document 2 in project 2
        async with self.apost(
            '/api/project/2/document/new',
            data=dict(name='otherdoc', description='Other one'),
            files=dict(
                file=('../otherdoc.html', 'text/plain', b'different content'),
            ),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"created": 2})
        db = self.application.DBSession()
        doc = db.query(database.Document).get(2)
        self.assertEqual(doc.name, 'otherdoc')
        self.assertEqual(doc.description, 'Other one')
        self.assertEqual(doc.filename, 'otherdoc.html')
        self.assertEqual(
            await poll_proj2,
            {'document_add': [{'description': 'Other one', 'document_id': 2,
                               'document_name': 'otherdoc'}], 'id': 4})
        poll_proj2 = await self.poll_event(2, 4)

        # Create highlight 1 in document 1
        async with self.apost(
            '/api/project/1/document/1/highlight/new',
            json=dict(start_offset=3, end_offset=7, tags=[1]),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"id": 1})
        self.assertEqual(
            await poll_proj1,
            {'highlight_add': {'1': [{'highlight_id': 1, 'tags': [1],
                                      'start_offset': 3, 'end_offset': 7}]},
             'id': 5, 'tag_count_changes': {'1': 1}})
        poll_proj1 = await self.poll_event(1, 5)

        # Change project 2 metadata
        async with self.apost(
            '/api/project/2',
            json={'name': 'new project', 'description': "Meaningful"},
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {})
        self.assertEqual(
            await poll_proj2,
            {'project_meta': {'project_name': 'new project',
                              'description': 'Meaningful'},
             'id': 6})
        poll_proj2 = await self.poll_event(2, 6)

        # Create document 3 in project 2
        async with self.apost(
            '/api/project/2/document/new',
            data=dict(name='third', description='Last one'),
            files=dict(file=(
                'C:\\Users\\Vicky\\Documents\\study.html',
                'text/html',
                b'<strong>Opinions</strong> and <em>facts</em>!',
            )),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"created": 3})
        self.assertEqual(
            await poll_proj2,
            {'document_add': [{'description': 'Last one', 'document_id': 3,
                               'document_name': 'third'}], 'id': 7})
        poll_proj2 = await self.poll_event(2, 7)

        # Create highlight in document 2, using wrong project id
        async with self.apost(
            '/api/project/1/document/2/highlight/new',
            json=dict(start_offset=0, end_offset=4, tags=[]),
        ) as response:
            self.assertEqual(response.status, 404)

        # Create highlight in document 2, using tags that don't exist
        async with self.apost(
            '/api/project/2/document/2/highlight/new',
            json=dict(start_offset=0, end_offset=4, tags=[150]),
        ) as response:
            self.assertEqual(response.status, 400)
            self.assertEqual(await response.json(),
                             {"error": "Tag not in project"})

        # Create highlight in document 2, using tags from project 1
        async with self.apost(
            '/api/project/2/document/2/highlight/new',
            json=dict(start_offset=0, end_offset=4, tags=[1]),
        ) as response:
            self.assertEqual(response.status, 400)
            self.assertEqual(await response.json(),
                             {"error": "Tag not in project"})

        # Create highlight 2 in document 2
        async with self.apost(
            '/api/project/2/document/2/highlight/new',
            json=dict(start_offset=0, end_offset=4, tags=[4]),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"id": 2})
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'2': [{'highlight_id': 2, 'tags': [4],
                                      'start_offset': 0, 'end_offset': 4}]},
             'id': 8, 'tag_count_changes': {'4': 1}})
        poll_proj2 = await self.poll_event(2, 8)

        # Create highlight 3 in document 2
        async with self.apost(
            '/api/project/2/document/2/highlight/new',
            json=dict(start_offset=13, end_offset=17, tags=[3, 2]),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"id": 3})
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'2': [{'highlight_id': 3, 'tags': [2, 3],
                                      'start_offset': 13, 'end_offset': 17}]},
             'id': 9, 'tag_count_changes': {'2': 1, '3': 1}})
        poll_proj2 = await self.poll_event(2, 9)

        # Create highlight 4 in document 3
        async with self.apost(
            '/api/project/2/document/3/highlight/new',
            json=dict(start_offset=0, end_offset=7, tags=[3]),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {"id": 4})
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'3': [{'highlight_id': 4, 'tags': [3],
                                      'start_offset': 0, 'end_offset': 7}]},
             'id': 10, 'tag_count_changes': {'3': 1}})
        poll_proj2 = await self.poll_event(2, 10)

        # List highlights in project 2 under 'people'
        async with self.aget('/api/project/2/highlights/people') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'highlights': [
                    {'id': 3, 'document_id': 2, 'tags': [2, 3],
                     'content': "tent"},
                    {'id': 4, 'document_id': 3, 'tags': [3],
                     'content': "<strong>Opinion</strong>"},
                ],
                'pages': 1,
            })

        # List highlights in project 2 under 'interesting.places'
        async with self.aget(
            '/api/project/2/highlights/interesting.places',
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'highlights': [
                    {'id': 2, 'document_id': 2, 'tags': [4],
                     'content': "diff"},
                ],
                'pages': 1,
            })

        # List highlights in project 2 under 'interesting'
        async with self.aget(
            '/api/project/2/highlights/interesting',
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'highlights': [
                    {'id': 2, 'document_id': 2, 'tags': [4],
                     'content': "diff"},
                    {'id': 3, 'document_id': 2, 'tags': [2, 3],
                     'content': "tent"},
                ],
                'pages': 1,
            })

        # List all highlights in project 2
        async with self.aget('/api/project/2/highlights/') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'highlights': [
                    {'id': 2, 'document_id': 2, 'tags': [4],
                     'content': "diff"},
                    {'id': 3, 'document_id': 2, 'tags': [2, 3],
                     'content': "tent"},
                    {'id': 4, 'document_id': 3, 'tags': [3],
                     'content': "<strong>Opinion</strong>"},
                ],
                'pages': 1,
            })

        # Get contents of document 2
        async with self.aget('/api/project/2/document/2/content') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'contents': [{'contents': 'different content', 'offset': 0}],
                'highlights': [
                    {'id': 2, 'start_offset': 0, 'end_offset': 4,
                     'tags': [4]},
                    {'id': 3, 'start_offset': 13, 'end_offset': 17,
                     'tags': [2, 3]},
                ],
            })

        # Export document 2 to HTML
        async with self.aget('/project/2/export/document/2.html') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers['Content-Type'],
                'text/html; charset=utf-8',
            )
            self.assertEqual(
                await response.text(),
                textwrap.dedent('''\
                <!DOCTYPE html>
                <html>
                  <head>
                    <meta charset="UTF-8">
                    <style>
                      .highlight {
                        background-color: #ff0;
                      }
                      .taglist {
                        font-style: oblique;
                        background: #fbb !important;
                      }
                    </style>
                    <title>otherdoc</title>
                  </head>
                  <body>
                    <h1>otherdoc</h1>
                <span class="highlight">diff</span>\
<span class="taglist"> [interesting.places]</span>erent con\
<span class="highlight">tent</span><span class="taglist"> \
[interesting, people]</span>
                  </body>
                </html>'''),
            )

        # Export document 2 to unknown format
        async with self.aget('/project/2/export/document/2.dat') as response:
            self.assertEqual(response.status, 404)
            self.assertEqual(response.headers['Content-Type'], 'text/plain')
            self.assertEqual(
                await response.text(),
                'Unsupported format: dat',
            )

        # Export highlights in project 2 under 'interesting' to HTML
        async with self.aget(
            '/project/2/export/highlights/interesting.html',
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                await response.text(),
                textwrap.dedent('''\
                    <!DOCTYPE html>
                    <html>
                      <head>
                        <meta charset="UTF-8">
                        <title></title>
                        <style>
                          h1 {
                            margin-bottom: 1em;
                          }
                        </style>
                      </head>
                      <body>
                        <h1>Taguette highlights: interesting</h1>

                        diff
                        <p>
                          <strong>Document:</strong> otherdoc
                          <strong>Tags:</strong>
                            interesting.places
                        </p>
                        <hr>

                        tent
                        <p>
                          <strong>Document:</strong> otherdoc
                          <strong>Tags:</strong>
                            interesting,
                            people
                        </p>

                      </body>
                    </html>'''),
            )

        # Export highlights in project 2 under 'interesting' to CSV
        async with self.aget(
            '/project/2/export/highlights/interesting.csv',
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                await response.text(),
                textwrap.dedent('''\
                id,document,tag,content
                2,otherdoc,interesting.places,diff
                3,otherdoc,interesting,tent
                3,otherdoc,people,tent
                ''').replace('\n', '\r\n'),
            )

        # Export codebook of project 2 to CSV
        async with self.aget('/project/2/export/codebook.csv') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers['Content-Type'],
                'text/csv; charset=utf-8',
            )
            self.assertEqual(
                await response.text(),
                textwrap.dedent('''\
                    tag,description,number of highlights
                    interesting,Further review required,1
                    people,People of interest,2
                    interesting.places,,1
                    ''').replace('\n', '\r\n'),
            )

        # Export codebook of project 2 to HTML
        async with self.aget('/project/2/export/codebook.html') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                await response.text(),
                textwrap.dedent('''\
                    <!DOCTYPE html>
                    <html>
                      <head>
                        <meta charset="UTF-8">
                        <style>
                          .highlight {
                            background-color: #ff0;
                          }
                        </style>
                        <title>Taguette Codebook</title>
                      </head>
                      <body>
                        <h1>Taguette Codebook</h1>

                          <h2>interesting</h2>
                          <p class="number">1 highlight</p>
                          <p>Further review required</p>

                          <h2>people</h2>
                          <p class="number">2 highlights</p>
                          <p>People of interest</p>

                          <h2>interesting.places</h2>
                          <p class="number">1 highlight</p>
                          <p></p>

                      </body>
                    </html>'''),
            )

        # Export codebook of project 2 to REFI-QDA
        async with self.aget('/project/2/export/codebook.qdc') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(
                response.headers['Content-Type'],
                'text/xml; charset=utf-8',
            )
            compare_xml(
                await response.text(),
                ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<CodeBook xmlns="urn:QDA-XML:codebook:1.0" origin="'
                 'Taguette {ver}"><Codes><Code guid="0D62985D-B147-5D01-A9B5-'
                 'CAE5DCD98342" name="interesting" isCodable="true"/><Code '
                 'guid="DFE5C38E-9449-5959-A1F7-E3D895CFA87F" name="people" '
                 'isCodable="true"/><Code guid="725F0645-9CD3-598A-8D2B-'
                 'EC3D39AB3C3F" name="interesting.places" isCodable="true"/>'
                 '</Codes><Sets/></CodeBook>'
                 ).format(ver=__version__),
            )

        # Merge tag 3 into 2
        async with self.apost(
            '/api/project/2/tag/merge',
            json=dict(src=3, dest=2),
        ) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {'id': 2})
        self.assertEqual(
            await poll_proj2,
            {'tag_merge': [{'src_tag_id': 3, 'dest_tag_id': 2}], 'id': 11},
        )
        poll_proj2 = await self.poll_event(2, 11)

        # List all highlights in project 2
        async with self.aget('/api/project/2/highlights/') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(await response.json(), {
                'highlights': [
                    {'id': 2, 'document_id': 2, 'tags': [4],
                     'content': "diff"},
                    {'id': 3, 'document_id': 2, 'tags': [2],
                     'content': "tent"},
                    {'id': 4, 'document_id': 3, 'tags': [2],
                     'content': "<strong>Opinion</strong>"},
                ],
                'pages': 1,
            })

        await asyncio.sleep(2)
        self.assertNotDone(poll_proj1)
        self.assertNotDone(poll_proj2)

    @gen_test
    async def test_reset_password(self):
        # Accept cookies
        async with self.apost('/cookies', data=dict()) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Fetch registration page
        async with self.aget('/register') as response:
            self.assertEqual(response.status, 200)

        # Register
        async with self.apost(
            '/register',
            data=dict(
                login='User',
                password1='pass1', password2='pass1',
                email='test@example.com',
            ),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # User exists in database
        db = self.application.DBSession()
        self.assertEqual(
            [
                (
                    user.login,
                    bool(user.hashed_password), bool(user.password_set_date),
                    user.check_password('pass1'),
                    user.check_password('pass2'),
                )
                for user in db.query(database.User).all()
            ],
            [
                ('admin', True, True, False, False),
                ('user', True, True, True, False),
            ],
        )

        # Log out
        async with self.aget('/logout') as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Wait so that reset link is more recent than password
        time.sleep(1)

        # Send reset link
        async with self.aget('/reset_password'):
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')
        with mock.patch.object(self.application, 'send_mail') as mo:
            async with self.apost(
                '/reset_password',
                data=dict(email='test@example.com'),
            ) as response:
                self.assertEqual(response.status, 200)
        msg = mo.call_args[0][0]
        content = msg.get_payload()[0].get_content()
        self.assertTrue(content.startswith("Someone has requested "))
        link = re.search(r'https:\S*', content).group(0)
        token = urlparse(link).query[12:]

        # Check wrong tokens don't work
        async with self.aget(
            '/new_password?reset_token=wrongtoken',
        ) as response:
            self.assertEqual(response.status, 403)
        async with self.apost(
            '/new_password',
            data=dict(
                reset_token='wrongtoken',
                password1='pass3', password2='pass3',
            ),
        ) as response:
            self.assertEqual(response.status, 403)

        # Check right token works
        async with self.aget('/new_password?reset_token=' + token) as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/new_password',
            data=dict(
                reset_token=token,
                password1='pass2', password2='pass2',
            ),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # User exists in database
        db = self.application.DBSession()
        self.assertEqual(
            [
                (
                    user.login,
                    bool(user.hashed_password), bool(user.password_set_date),
                    user.check_password('pass1'),
                    user.check_password('pass2'),
                )
                for user in db.query(database.User).all()
            ],
            [
                ('admin', True, True, False, False),
                ('user', True, True, False, True),
            ],
        )

        # Check token doesn't work anymore
        async with self.apost(
            '/new_password',
            data=dict(
                reset_token=token,
                password1='pass4', password2='pass4',
            ),
        ) as response:
            self.assertEqual(response.status, 403)
        async with self.aget('/new_password?reset_token=' + token) as response:
            self.assertEqual(response.status, 403)

    @classmethod
    def make_basic_db(cls, db, db_num):
        # Populate database
        user = database.User(login='db%duser' % db_num)
        user.set_password('hackme')
        db.add(user)
        cls.make_basic_project(db, db_num, 1)
        cls.make_basic_project(db, db_num, 2)

    @staticmethod
    def make_basic_project(db, db_num, project_num):
        # Creates 1 project, 2 (+1 deleted) documents, 2 (+1 deleted) tags,
        # 2 (+1 deleted) highlights, 13 commands total
        def doc(project, number):
            text = 'db%ddoc%d%d' % (db_num, project_num, number)
            return database.Document(
                name=text + '.txt',
                description='',
                filename=text + '.txt',
                project=project,
                contents=text,
            )

        user = 'db%duser' % db_num
        project1 = database.Project(
            name='db%dproject%d' % (db_num, project_num),
            description='',
        )
        db.add(project1)
        db.flush()
        document1 = doc(project1, 1)
        db.add(document1)
        document2 = doc(project1, 2)
        db.add(document2)
        tag1 = database.Tag(
            project=project1,
            path='db%dtag%d1' % (db_num, project_num),
            description='',
        )
        db.add(tag1)
        tag2 = database.Tag(
            project=project1,
            path='db%dtag%d2' % (db_num, project_num),
            description='',
        )
        db.add(tag2)
        db.flush()
        hl1 = database.Highlight(
            document_id=document1.id,
            start_offset=3, end_offset=6, snippet='doc',
        )
        hl2 = database.Highlight(
            document_id=document2.id,
            start_offset=3, end_offset=6, snippet='doc',
        )
        db.add(hl1)
        db.add(hl2)
        db.flush()
        db.add(database.HighlightTag(highlight_id=hl1.id, tag_id=tag2.id))
        db.add(database.HighlightTag(highlight_id=hl2.id, tag_id=tag1.id))
        db.add(database.ProjectMember(user_login='admin', project=project1,
                                      privileges=database.Privileges.ADMIN))
        db.add(database.ProjectMember(user_login=user,
                                      project=project1,
                                      privileges=database.Privileges.ADMIN))
        db.add(database.Command.document_add(user, document1))
        document_fake = doc(project1, 100)
        db.add(document_fake)
        db.flush()
        db.add(database.Command.document_add(user, document_fake))
        db.add(database.Command.document_add(user, document2))
        db.add(database.Command.document_delete(user, document_fake))
        db.delete(document_fake)
        tag_fake = database.Tag(project=project1, path='db%dtagF' % db_num,
                                description='')
        db.add(tag_fake)
        db.flush()
        db.add(database.Command.tag_add(user, tag1))
        db.add(database.Command.tag_add(user, tag_fake))
        db.add(database.Command.tag_add(user, tag2))
        db.add(database.Command.tag_delete(user, project1.id, tag_fake.id))
        db.delete(tag_fake)
        hl_fake = database.Highlight(
            document_id=document1.id,
            start_offset=3, end_offset=6, snippet='doc',
        )
        db.add(hl_fake)
        db.flush()
        db.add(database.Command.highlight_add(user, document1, hl1, []))
        db.add(database.Command.highlight_add(user, document1, hl1, [tag2.id]))
        db.add(database.Command.highlight_add(user, document1, hl_fake,
                                              [tag1.id]))
        db.add(database.Command.highlight_add(user, document1, hl2, [tag1.id]))
        db.add(database.Command.highlight_delete(user, document1, hl_fake.id))
        db.delete(hl_fake)

    def assertRowsEqualsExceptDates(self, first, second):
        self.assertEqual(*[
            [
                [item for item in row if not isinstance(item, datetime)]
                for row in rows]
            for rows in (first, second)
        ])

    @with_tempdir
    @gen_test
    async def test_import(self, tmp):
        # Populate database
        db1 = self.application.DBSession()
        self.make_basic_db(db1, 1)
        db1.commit()

        # Login
        async with self.apost('/cookies', data=dict()) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')
        async with self.aget('/login') as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/login',
            data=dict(next='/', login='db1user', password='hackme'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Create second database
        db2_path = os.path.join(tmp, 'db.sqlite3')
        db2 = database.connect('sqlite:///' + db2_path)()
        db2.add(database.User(login='admin'))
        self.make_basic_db(db2, 2)
        db2.commit()

        # List projects in database
        with open(db2_path, 'rb') as fp:
            async with self.apost(
                '/api/import',
                data={},
                files=dict(file=('db2.sqlite3', 'application/octet-stream',
                                 fp.read())),
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.json(), {
                    'projects': [{'id': 1, 'name': 'db2project1'},
                                 {'id': 2, 'name': 'db2project2'}],
                })

        # Import project
        with open(db2_path, 'rb') as fp:
            async with self.apost(
                '/api/import',
                data={'project_id': '1'},
                files=dict(file=('db2.sqlite3', 'application/octet-stream',
                                 fp.read())),
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(await response.json(), {
                    'project_id': 3,
                })

        # Check imported project
        self.assertEqual(
            {row[0] for row in db1.execute(
                sqlalchemy.select([database.User.__table__.c.login])
            )},
            {'admin', 'db1user'},
        )
        self.assertRowsEqualsExceptDates(
            db1.execute(
                database.Project.__table__.select()
                .order_by(database.Project.__table__.c.id)
            ),
            [
                (1, 'db1project1', '', datetime.utcnow()),
                (2, 'db1project2', '', datetime.utcnow()),
                (3, 'db2project1', '', datetime.utcnow()),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db1.execute(
                database.ProjectMember.__table__.select()
                .order_by(database.ProjectMember.__table__.c.project_id)
                .order_by(database.ProjectMember.__table__.c.user_login)
            ),
            [
                (1, 'admin', database.Privileges.ADMIN),
                (1, 'db1user', database.Privileges.ADMIN),
                (2, 'admin', database.Privileges.ADMIN),
                (2, 'db1user', database.Privileges.ADMIN),
                (3, 'db1user', database.Privileges.ADMIN),
            ],
        )
        self.assertEqual(
            [
                (row['id'], row['name'])
                for row in db1.execute(
                    database.Document.__table__.select()
                    .order_by(database.Document.__table__.c.id)
                )
            ],
            [
                (1, 'db1doc11.txt'),
                (2, 'db1doc12.txt'),
                (4, 'db1doc21.txt'),
                (5, 'db1doc22.txt'),
                (7, 'db2doc11.txt'),
                (8, 'db2doc12.txt'),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db1.execute(
                database.Command.__table__.select()
                .where(database.Command.__table__.c.project_id == 3)
                .order_by(database.Command.__table__.c.id)
            ),
            [
                # id, user_login, project_id, document_id, {payload}
                # project 1 imported as 3
                # documents 1, 2, 3 imported as 7, 8, 9
                # tags 1, 2, 3 imported as 7, 8, -3
                # highlights 1, 2, 3 imported as 7, 8, -3
                # commands 1-13 exported as 27-39
                (27, 'db1user', 3, 7,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db2doc11.txt'}),
                (28, 'db1user', 3, -3,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db2doc1100.txt'}),
                (29, 'db1user', 3, 8,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db2doc12.txt'}),
                (30, 'db1user', 3, -3, {'type': 'document_delete'}),
                (31, 'db1user', 3, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': 7,
                  'tag_path': 'db2tag11'}),
                (32, 'db1user', 3, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': -3,
                  'tag_path': 'db2tagF'}),
                (33, 'db1user', 3, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': 8,
                  'tag_path': 'db2tag12'}),
                (34, 'db1user', 3, None, {'type': 'tag_delete', 'tag_id': -3}),
                (35, 'db1user', 3, 7,
                 {'type': 'highlight_add', 'highlight_id': 7,
                  'start_offset': 3, 'end_offset': 6, 'tags': []}),
                (36, 'db1user', 3, 7,
                 {'type': 'highlight_add', 'highlight_id': 7,
                  'start_offset': 3, 'end_offset': 6, 'tags': [8]}),
                (37, 'db1user', 3, 7,
                 {'type': 'highlight_add', 'highlight_id': -3,
                  'start_offset': 3, 'end_offset': 6, 'tags': [7]}),
                (38, 'db1user', 3, 7,
                 {'type': 'highlight_add', 'highlight_id': 8,
                  'start_offset': 3, 'end_offset': 6, 'tags': [7]}),
                (39, 'db1user', 3, 7,
                 {'type': 'highlight_delete', 'highlight_id': -3}),
                (40, 'db1user', 3, None, {'type': 'project_import'}),
            ],
        )
        self.assertEqual(
            [
                (row['id'], row['document_id'])
                for row in db1.execute(
                    database.Highlight.__table__.select()
                    .order_by(database.Highlight.__table__.c.id)
                )
            ],
            [(1, 1), (2, 2), (4, 4), (5, 5), (7, 7), (8, 8)],
        )
        self.assertRowsEqualsExceptDates(
            db1.execute(database.Tag.__table__.select()),
            [
                (1, 1, 'db1tag11', ''),
                (2, 1, 'db1tag12', ''),
                (4, 2, 'db1tag21', ''),
                (5, 2, 'db1tag22', ''),
                (7, 3, 'db2tag11', ''),
                (8, 3, 'db2tag12', ''),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db1.execute(
                database.HighlightTag.__table__.select()
                .order_by(database.HighlightTag.__table__.c.highlight_id)
            ),
            [(1, 2), (2, 1), (4, 5), (5, 4), (7, 8), (8, 7)],
        )

    @with_tempdir
    @gen_test
    async def test_export(self, tmp):
        # Populate database
        db1 = self.application.DBSession()
        self.make_basic_db(db1, 1)
        db1.commit()

        # Login
        async with self.apost('/cookies', data=dict()) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')
        async with self.aget('/login') as response:
            self.assertEqual(response.status, 200)
        async with self.apost(
            '/login',
            data=dict(next='/', login='db1user', password='hackme'),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Export project
        db2_path = os.path.join(tmp, 'db.sqlite3')
        async with self.aget('/project/2/export/project.sqlite3') as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers['Content-Type'],
                             'application/vnd.sqlite3')
            self.assertTrue(re.match(
                '^attachment; filename='
                + '"[0-9]{4}-[0-9]{2}-[0-9]{2}_db1project2.sqlite3"$',
                response.headers['Content-Disposition'],
            ))
            with open(db2_path, 'wb') as fp:
                fp.write(await response.read())
        db2 = database.connect('sqlite:///' + db2_path)()

        # Check exported project
        self.assertEqual(
            {row[0] for row in db2.execute(
                sqlalchemy.select([database.User.__table__.c.login])
            )},
            {'admin'},
        )
        self.assertRowsEqualsExceptDates(
            db2.execute(
                database.Project.__table__.select()
                .order_by(database.Project.__table__.c.id)
            ),
            [
                (1, 'db1project2', '', datetime.utcnow()),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db2.execute(
                database.ProjectMember.__table__.select()
                .order_by(database.ProjectMember.__table__.c.user_login)
            ),
            [
                (1, 'admin', database.Privileges.ADMIN),
            ],
        )
        self.assertEqual(
            [
                (row['id'], row['name'])
                for row in db2.execute(
                    database.Document.__table__.select()
                    .order_by(database.Document.__table__.c.id)
                )
            ],
            [
                (1, 'db1doc21.txt'),
                (2, 'db1doc22.txt'),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db2.execute(
                database.Command.__table__.select()
                .order_by(database.Command.__table__.c.id)
            ),
            [
                # id, user_login, project_id, document_id, {payload}
                # project 2 exported as 1
                # documents 4, 5, 6 exported as 1, 2, -6
                # tags 4, 5, 6 exported as 1, 2, -6
                # highlights 4, 5, 6 exported as 1, 2, -6
                # commands 14-26 exported as 1-13
                (1, 'admin', 1, 1,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db1doc21.txt'}),
                (2, 'admin', 1, -6,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db1doc2100.txt'}),
                (3, 'admin', 1, 2,
                 {'type': 'document_add', 'description': '',
                  'document_name': 'db1doc22.txt'}),
                (4, 'admin', 1, -6, {'type': 'document_delete'}),
                (5, 'admin', 1, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': 1,
                  'tag_path': 'db1tag21'}),
                (6, 'admin', 1, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': -6,
                  'tag_path': 'db1tagF'}),
                (7, 'admin', 1, None,
                 {'type': 'tag_add', 'description': '', 'tag_id': 2,
                  'tag_path': 'db1tag22'}),
                (8, 'admin', 1, None,
                 {'type': 'tag_delete', 'tag_id': -6}),
                (9, 'admin', 1, 1,
                 {'type': 'highlight_add', 'highlight_id': 1,
                  'start_offset': 3, 'end_offset': 6, 'tags': []}),
                (10, 'admin', 1, 1,
                 {'type': 'highlight_add', 'highlight_id': 1,
                  'start_offset': 3, 'end_offset': 6, 'tags': [2]}),
                (11, 'admin', 1, 1,
                 {'type': 'highlight_add', 'highlight_id': -6,
                  'start_offset': 3, 'end_offset': 6, 'tags': [1]}),
                (12, 'admin', 1, 1,
                 {'type': 'highlight_add', 'highlight_id': 2,
                  'start_offset': 3, 'end_offset': 6, 'tags': [1]}),
                (13, 'admin', 1, 1,
                 {'type': 'highlight_delete', 'highlight_id': -6}),
            ],
        )
        self.assertEqual(
            [
                (row['id'], row['document_id'])
                for row in db2.execute(
                    database.Highlight.__table__.select()
                    .order_by(database.Highlight.__table__.c.id)
                )
            ],
            [(1, 1), (2, 2)],
        )
        self.assertRowsEqualsExceptDates(
            db2.execute(
                database.Tag.__table__.select()
                .order_by(database.Tag.__table__.c.id)
            ),
            [
                (1, 1, 'db1tag21', ''),
                (2, 1, 'db1tag22', ''),
            ],
        )
        self.assertRowsEqualsExceptDates(
            db2.execute(
                database.HighlightTag.__table__.select()
                .order_by(database.HighlightTag.__table__.c.highlight_id)
            ),
            [(1, 2), (2, 1)],
        )

    async def _poll_event(self, proj, from_id):
        async with self.aget(
            '/api/project/%d/events?from=%d' % (proj, from_id),
        ) as response:
            self.assertEqual(response.status, 200)
            return await response.json()

    async def poll_event(self, proj, from_id):
        fut = asyncio.ensure_future(self._poll_event(proj, from_id))
        await asyncio.sleep(0.2)  # Give time for the request to be sent
        return fut

    def assertNotDone(self, fut):
        self.assertTrue(fut.cancel())


class TestSingleuser(MyHTTPTestCase):
    def get_app(self):
        with mock.patch.object(web.Application, '_set_password',
                               new=set_dumb_password):
            self.application = web.make_app(
                dict(
                    main.DEFAULT_CONFIG,
                    NAME="Test Taguette instance", PORT=7465,
                    DATABASE=DATABASE_URI,
                    TOS_FILE=None,
                    EMAIL='test@example.com',
                    MAIL_SERVER={'host': 'localhost', 'port': 25},
                    COOKIES_PROMPT=False,
                    MULTIUSER=False,
                    SECRET_KEY='bq7ZoAtO7LtRJJ4P0iHSdH8yvcmCqynfeGB+x9y1',
                ),
                xsrf_cookies=False,
            )
            return self.application

    def tearDown(self):
        super(TestSingleuser, self).tearDown()
        close_all_sessions()
        engine = sqlalchemy.create_engine(DATABASE_URI)
        database.Base.metadata.drop_all(bind=engine)

    @gen_test
    async def test_login(self):
        # Fetch index, should have welcome message and no register link
        async with self.aget('/') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(
                b'did not supply a secret token',
                await response.read())
            self.assertNotIn(
                b'Register now</a> for free and get started',
                await response.read(),
            )

        # Only admin so far
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin'])

        # Fetch registration page: fails
        async with self.aget('/register') as response:
            self.assertEqual(response.status, 404)

        # Register: fails
        async with self.apost(
            '/register',
            data=dict(
                login='tester',
                password1='hacktoo', password2='hacktoo',
            ),
        ) as response:
            self.assertEqual(response.status, 404)

        # Authenticate with token
        async with self.aget(
            '/?token=' + self.application.single_user_token,
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Fetch index, should have project list
        async with self.aget('/') as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b'>Welcome!</h1>', await response.read())
            self.assertIn(b'Here are your projects', await response.read())

        # Fetch project creation page
        async with self.aget('/project/new') as response:
            self.assertEqual(response.status, 200)

        # Create a project
        async with self.apost(
            '/project/new',
            data=dict(name='test project', description=''),
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/project/1')

        # Fetch logout page
        async with self.aget('/logout') as response:
            self.assertEqual(response.status, 404)

    @gen_test
    async def test_project(self):
        db = self.application.DBSession()
        projects = [
            database.Project(name="first project", description=""),
            database.Project(name="a test", description="Test project"),
            database.Project(name="private P", description="admin can't see"),
            database.Project(name="last project", description="Other"),
        ]
        for project in projects:
            db.add(project)
        db.commit()
        for i in [1, 2, 4]:
            db.add(database.ProjectMember(
                project_id=i,
                user_login='admin',
                privileges=database.Privileges.ADMIN))
        db.commit()

        # Authenticate with token
        async with self.aget(
            '/?token=' + self.application.single_user_token,
        ) as response:
            self.assertEqual(response.status, 302)
            self.assertEqual(response.headers['Location'], '/')

        # Check project list
        async with self.aget('/') as response:
            self.assertEqual(response.status, 200)
            body = await response.read()
        self.assertIn(b"first project", body)
        self.assertIn(b"a test", body)
        self.assertNotIn(b"private P", body)
        self.assertIn(b"last project", body)


if __name__ == '__main__':
    unittest.main()
