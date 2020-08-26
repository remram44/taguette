import asyncio
from http.cookies import SimpleCookie
import itertools
import json
import os
import random
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import close_all_sessions
import string
import textwrap
import time
from tornado.testing import AsyncTestCase, gen_test, AsyncHTTPTestCase, \
    get_async_test_timeout
import unittest
from unittest import mock
from urllib.parse import urlencode, urlparse

from taguette import convert, database, extract, main, validate, web


if 'TAGUETTE_TEST_DB' in os.environ:
    DATABASE_URI = os.environ['TAGUETTE_TEST_DB']
else:
    DATABASE_URI = 'sqlite://'


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


class MyHTTPTestCase(AsyncHTTPTestCase):
    xsrf = None

    def setUp(self):
        web.Application.check_messages = lambda *a: None
        validate.filename.windows = True  # escape device names
        super(MyHTTPTestCase, self).setUp()
        self.cookie = SimpleCookie()

    _re_xsrf = re.compile(
        br'<input type="hidden" name="_xsrf" value="([^">]+)" */?>')

    def update(self, response):
        if response.code < 400:
            m = self._re_xsrf.search(response.body)
            if m is not None:
                self.xsrf = m.group(1).decode('utf-8')
            if 'Set-Cookie' in response.headers:
                self.cookie.load(response.headers['Set-Cookie'])

    def get_cookie(self):
        # Python's cookies lib makes multiple headers, which is invalid
        return '; '.join('%s=%s' % (k, v.value)
                         for k, v in self.cookie.items())

    def _fetch(self, url, **kwargs):
        # Copied from tornado.testing.AsyncHTTPTestCase.fetch()
        if not url.lower().startswith(('http://', 'https://')):
            url = self.get_url(url)
        return self.http_client.fetch(url, raise_error=False, **kwargs)

    async def aget(self, url):
        headers = {}
        headers['Cookie'] = self.get_cookie()
        response = self._fetch(url, follow_redirects=False,
                               headers=headers)
        response = await response
        self.update(response)
        return response

    async def apost(self, url, args, fmt='form', files={}):
        if fmt == 'form':
            headers = {'Content-Type': 'application/x-www-form-urlencoded',
                       'Cookie': self.get_cookie()}
            body = urlencode(dict(args, _xsrf=self.xsrf))
        elif fmt == 'json':
            url = '%s%s%s' % (url, '&' if '?' in url else '?',
                              urlencode(dict(_xsrf=self.xsrf)))
            headers = {'Content-Type': 'application/json',
                       'Accept': 'application/json',
                       'Cookie': self.get_cookie()}
            body = json.dumps(args)
        elif fmt == 'multipart':
            headers = {'Content-Type': 'multipart/form-data; charset=utf-8; '
                                       'boundary=-sep',
                       'Cookie': self.get_cookie()}
            body = []
            for k, v in dict(args, _xsrf=self.xsrf).items():
                body.append(('---sep\r\nContent-Disposition: form-data; '
                             'name="%s"\r\n' % k).encode('utf-8'))
                body.append(v.encode('utf-8'))
            for k, v in files.items():
                body.append(('---sep\r\nContent-Disposition: form-data; name='
                             '"%s"; filename="%s"\r\nContent-Type: %s\r\n' % (
                                 k, v[0], v[1])).encode('utf-8'))
                body.append(v[2])
            body.append(b'---sep--\r\n')
            body = b'\r\n'.join(body)
        else:
            raise ValueError
        response = self._fetch(url, method='POST', follow_redirects=False,
                               headers=headers, body=body)
        response = await response
        self.update(response)
        return response

    def get(self, url):
        return self.io_loop.run_sync(
            lambda: self.aget(url),
            timeout=get_async_test_timeout())

    def post(self, url, args):
        return self.io_loop.run_sync(
            lambda: self.apost(url, args),
            timeout=get_async_test_timeout())


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
                EMAIL='test@example.com',
                MAIL_SERVER={'host': 'localhost', 'port': 25},
                COOKIES_PROMPT=True,
                MULTIUSER=True,
                SECRET_KEY='2PbQ/5Rs005G/nTuWfibaZTUAo3Isng3QuRirmBK',
            ))
            return self.application

    def tearDown(self):
        close_all_sessions()
        engine = create_engine(DATABASE_URI)
        database.Base.metadata.drop_all(bind=engine)

    def test_login(self):
        # Fetch index, should have welcome message and register link
        response = self.get('/')
        self.assertEqual(response.code, 200)
        self.assertIn(b'>Welcome</h1>', response.body)
        self.assertIn(b'Register now</a> for free and get started',
                      response.body)

        # Only admin so far
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin'])

        # Fetch registration page, should hit cookies prompt
        response = self.get('/register')
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'],
                         '/cookies?next=%2Fregister')

        # Accept cookies
        response = self.post('/cookies', dict(next='/register'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/register')

        # Fetch registration page
        response = self.get('/register')
        self.assertEqual(response.code, 200)

        # Register
        response = self.post(
            '/register', dict(login='Tester',
                              password1='hacktoo', password2='hacktoo'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # User exists in database
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin', 'tester'])

        # Fetch index, should have project list
        response = self.get('/')
        self.assertEqual(response.code, 200)
        self.assertIn(b'>Welcome tester</h1>', response.body)
        self.assertIn(b'Here are your projects', response.body)

        # Fetch project creation page
        response = self.get('/project/new')
        self.assertEqual(response.code, 200)

        # Create a project
        response = self.post(
            '/project/new', dict(name='test project', description=''))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/1')

        # Log out
        response = self.get('/logout')
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Hit error page
        response = self.get('/api/project/1/highlights/')
        self.assertEqual(response.code, 403)
        self.assertEqual(response.body, b'{"error": "Not logged in"}')

        # Fetch login page
        response = self.get('/login?' + urlencode(dict(next='/project/1')))
        self.assertEqual(response.code, 200)

        # Log in
        response = self.post('/login',
                             dict(next='/project/1', login='admin',
                                  password='hackme'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/1')

    @gen_test(timeout=30)
    async def test_projects(self):
        # Accept cookies
        response = await self.apost('/cookies', dict())
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Log in
        response = await self.aget('/login')
        self.assertEqual(response.code, 200)
        response = await self.apost('/login', dict(next='/', login='admin',
                                                   password='hackme'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Create project 1
        response = await self.aget('/project/new')
        self.assertEqual(response.code, 200)
        response = await self.apost('/project/new', dict(
            name='\uFF9F\uFF65\u273F\u30FE\u2572\x28\uFF61\u25D5\u203F\u25D5'
                 '\uFF61\x29\u2571\u273F\uFF65\uFF9F',
            description="R\xE9mi's project"))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/1')

        # Check project page
        response = await self.aget('/project/1')
        self.assertEqual(response.code, 200)
        body = response.body.decode('utf-8')
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
        response = await self.aget('/project/new')
        self.assertEqual(response.code, 200)
        response = await self.apost('/project/new', dict(name='other project',
                                                         description=''))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/2')

        # Start polling
        poll_proj2 = await self.poll_event(2, -1)

        # Create tags in project 2
        response = await self.apost('/api/project/2/tag/new',
                                    dict(path='people',
                                         description="People of interest"),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(
            await poll_proj2,
            {'tag_add': [{'description': "People of interest", 'id': 3,
                          'path': 'people'}],
             'id': 1})
        poll_proj2 = await self.poll_event(2, 1)

        response = await self.apost('/api/project/2/tag/new',
                                    dict(path='interesting.places',
                                         description=''),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(
            await poll_proj2,
            {'tag_add': [{'description': '', 'id': 4,
                          'path': 'interesting.places'}],
             'id': 2})
        poll_proj2 = await self.poll_event(2, 2)

        # Create document 1 in project 1
        name = '\u03A9\u2248\xE7\u221A\u222B\u02DC\xB5\u2264\u2265\xF7'
        response = await self.apost('/api/project/1/document/new',
                                    dict(name=name, description=''),
                                    fmt='multipart',
                                    files=dict(file=('../NUL.html',
                                                     'text/plain',
                                                     b'content here')))
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"created": 1}')
        db = self.application.DBSession()
        doc = db.query(database.Document).get(1)
        self.assertEqual(doc.name, name)
        self.assertEqual(doc.description, '')
        self.assertEqual(doc.filename, '_NUL.html')
        self.assertEqual(
            await poll_proj1,
            {'document_add': [{'description': '', 'id': 1, 'name': name}],
             'id': 3})
        poll_proj1 = await self.poll_event(1, 3)

        # Create document 2 in project 2
        response = await self.apost('/api/project/2/document/new',
                                    dict(name='otherdoc',
                                         description='Other one'),
                                    fmt='multipart',
                                    files=dict(file=('../otherdoc.html',
                                                     'text/plain',
                                                     b'different content')))
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"created": 2}')
        db = self.application.DBSession()
        doc = db.query(database.Document).get(2)
        self.assertEqual(doc.name, 'otherdoc')
        self.assertEqual(doc.description, 'Other one')
        self.assertEqual(doc.filename, 'otherdoc.html')
        self.assertEqual(
            await poll_proj2,
            {'document_add': [{'description': 'Other one', 'id': 2,
                               'name': 'otherdoc'}], 'id': 4})
        poll_proj2 = await self.poll_event(2, 4)

        # Create highlight 1 in document 1
        response = await self.apost('/api/project/1/document/1/highlight/new',
                                    dict(start_offset=3, end_offset=7,
                                         tags=[1]),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"id": 1}')
        self.assertEqual(
            await poll_proj1,
            {'highlight_add': {'1': [{'id': 1, 'tags': [1],
                                      'start_offset': 3, 'end_offset': 7}]},
             'id': 5, 'tag_count_changes': {'1': 1}})
        poll_proj1 = await self.poll_event(1, 5)

        # Change project 2 metadata
        response = await self.apost('/api/project/2',
                                    {'name': 'new project',
                                     'description': "Meaningful"},
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{}')
        self.assertEqual(
            await poll_proj2,
            {'project_meta': {'name': 'new project',
                              'description': 'Meaningful'},
             'id': 6})
        poll_proj2 = await self.poll_event(2, 6)

        # Create document 3 in project 2
        response = await self.apost(
            '/api/project/2/document/new',
            dict(name='third',
                 description='Last one'),
            fmt='multipart',
            files=dict(file=(
                'C:\\Users\\Vicky\\Documents\\study.html',
                'text/html',
                b'<strong>Opinions</strong> and <em>facts</em>!',
            )),
        )
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"created": 3}')
        self.assertEqual(
            await poll_proj2,
            {'document_add': [{'description': 'Last one', 'id': 3,
                               'name': 'third'}], 'id': 7})
        poll_proj2 = await self.poll_event(2, 7)

        # Create highlight in document 2, using wrong project id
        response = await self.apost('/api/project/1/document/2/highlight/new',
                                    dict(start_offset=0, end_offset=4,
                                         tags=[2]),
                                    fmt='json')
        self.assertEqual(response.code, 404)

        # Create highlight 2 in document 2
        response = await self.apost('/api/project/2/document/2/highlight/new',
                                    dict(start_offset=0, end_offset=4,
                                         tags=[4]),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"id": 2}')
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'2': [{'id': 2, 'tags': [4],
                                      'start_offset': 0, 'end_offset': 4}]},
             'id': 8, 'tag_count_changes': {'4': 1}})
        poll_proj2 = await self.poll_event(2, 8)

        # Create highlight 3 in document 2
        response = await self.apost('/api/project/2/document/2/highlight/new',
                                    dict(start_offset=13, end_offset=17,
                                         tags=[3, 2]),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"id": 3}')
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'2': [{'id': 3, 'tags': [2, 3],
                                      'start_offset': 13, 'end_offset': 17}]},
             'id': 9, 'tag_count_changes': {'2': 1, '3': 1}})
        poll_proj2 = await self.poll_event(2, 9)

        # Create highlight 4 in document 3
        response = await self.apost('/api/project/2/document/3/highlight/new',
                                    dict(start_offset=0, end_offset=7,
                                         tags=[3]),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'{"id": 4}')
        self.assertEqual(
            await poll_proj2,
            {'highlight_add': {'3': [{'id': 4, 'tags': [3],
                                      'start_offset': 0, 'end_offset': 7}]},
             'id': 10, 'tag_count_changes': {'3': 1}})
        poll_proj2 = await self.poll_event(2, 10)

        # List highlights in project 2 under 'people'
        response = await self.aget('/api/project/2/highlights/people')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')),
                         {'highlights': [
                             {'id': 3, 'document_id': 2, 'tags': [2, 3],
                              'content': "tent"},
                             {'id': 4, 'document_id': 3, 'tags': [3],
                              'content': "<strong>Opinion</strong>"},
                         ]})

        # List highlights in project 2 under 'interesting.places'
        response = await self.aget('/api/project/2/highlights/interesting.'
                                   'places')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')),
                         {'highlights': [
                             {'id': 2, 'document_id': 2, 'tags': [4],
                              'content': "diff"},
                         ]})

        # List highlights in project 2 under 'interesting'
        response = await self.aget('/api/project/2/highlights/interesting.'
                                   'places')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')),
                         {'highlights': [
                             {'id': 2, 'document_id': 2, 'tags': [4],
                              'content': "diff"},
                         ]})

        # List all highlights in project 2
        response = await self.aget('/api/project/2/highlights/')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')),
                         {'highlights': [
                             {'id': 2, 'document_id': 2, 'tags': [4],
                              'content': "diff"},
                             {'id': 3, 'document_id': 2, 'tags': [2, 3],
                              'content': "tent"},
                             {'id': 4, 'document_id': 3, 'tags': [3],
                              'content': "<strong>Opinion</strong>"},
                         ]})

        # Export to HTML
        response = await self.aget('/project/2/export/document/2.html')
        self.assertEqual(response.code, 200)
        self.assertEqual(
            response.body.decode('utf-8'),
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

        # Merge tag 3 into 2
        response = await self.apost('/api/project/2/tag/merge',
                                    dict(src=3, dest=2),
                                    fmt='json')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')), {'id': 2})
        self.assertEqual(
            await poll_proj2,
            {'tag_merge': [{'src': 3, 'dest': 2}], 'id': 11},
        )
        poll_proj2 = await self.poll_event(2, 11)

        # List all highlights in project 2
        response = await self.aget('/api/project/2/highlights/')
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body.decode('utf-8')),
                         {'highlights': [
                             {'id': 2, 'document_id': 2, 'tags': [4],
                              'content': "diff"},
                             {'id': 3, 'document_id': 2, 'tags': [2],
                              'content': "tent"},
                             {'id': 4, 'document_id': 3, 'tags': [2],
                              'content': "<strong>Opinion</strong>"},
                         ]})

        await asyncio.sleep(2)
        self.assertNotDone(poll_proj1)
        self.assertNotDone(poll_proj2)

    def test_reset_password(self):
        # Accept cookies
        response = self.post('/cookies', dict())
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Fetch registration page
        response = self.get('/register')
        self.assertEqual(response.code, 200)

        # Register
        response = self.post('/register', dict(login='User',
                                               password1='hackme',
                                               password2='hackme',
                                               email='test@example.com'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # User exists in database
        db = self.application.DBSession()
        self.assertEqual(
            [
                (
                    user.login,
                    bool(user.hashed_password), bool(user.password_set_date),
                )
                for user in db.query(database.User).all()
            ],
            [
                ('admin', True, True),
                ('user', True, True),
            ],
        )

        # Log out
        response = self.get('/logout')
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Wait so that reset link is more recent than password
        time.sleep(1)

        # Send reset link
        self.get('/reset_password')
        with mock.patch.object(self.application, 'send_mail') as mo:
            response = self.post('/reset_password',
                                 dict(email='test@example.com'))
        self.assertEqual(response.code, 200)
        msg = mo.call_args[0][0]
        content = msg.get_payload()[0].get_content()
        self.assertTrue(content.startswith("Someone has requested "))
        link = re.search(r'https:\S*', content).group(0)
        token = urlparse(link).query[12:]

        # Check wrong tokens don't work
        response = self.get('/new_password?reset_token=wrongtoken')
        self.assertEqual(response.code, 403)
        response = self.post(
            '/new_password',
            dict(
                reset_token='wrongtoken',
                password1='tagada', password2='tagada',
            ),
        )
        self.assertEqual(response.code, 403)

        # Check right token works
        response = self.get('/new_password?reset_token=' + token)
        self.assertEqual(response.code, 200)
        response = self.post(
            '/new_password',
            dict(
                reset_token=token,
                password1='tagada', password2='tagada',
            ),
        )
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Check token doesn't work anymore
        response = self.post(
            '/new_password',
            dict(
                reset_token=token,
                password1='tagada', password2='tagada',
            ),
        )
        self.assertEqual(response.code, 403)
        response = self.get('/new_password?reset_token=' + token)
        self.assertEqual(response.code, 403)

    async def _poll_event(self, proj, from_id):
        response = await self.aget('/api/project/%d/events?from=%d' % (
                                   proj, from_id))
        self.assertEqual(response.code, 200)
        return json.loads(response.body.decode('utf-8'))

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
        close_all_sessions()
        engine = create_engine(DATABASE_URI)
        database.Base.metadata.drop_all(bind=engine)

    def test_login(self):
        # Fetch index, should have welcome message and no register link
        response = self.get('/')
        self.assertEqual(response.code, 200)
        self.assertIn(b'did not supply a secret token', response.body)
        self.assertNotIn(b'Register now</a> for free and get started',
                         response.body)

        # Only admin so far
        db = self.application.DBSession()
        self.assertEqual([user.login
                          for user in db.query(database.User).all()],
                         ['admin'])

        # Fetch registration page: fails
        response = self.get('/register')
        self.assertEqual(response.code, 404)

        # Register: fails
        response = self.post(
            '/register', dict(login='tester',
                              password1='hacktoo', password2='hacktoo'))
        self.assertEqual(response.code, 404)

        # Authenticate with token
        response = self.get('/?token=' + self.application.single_user_token)
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Fetch index, should have project list
        response = self.get('/')
        self.assertEqual(response.code, 200)
        self.assertIn(b'>Welcome!</h1>', response.body)
        self.assertIn(b'Here are your projects', response.body)

        # Fetch project creation page
        response = self.get('/project/new')
        self.assertEqual(response.code, 200)

        # Create a project
        response = self.post(
            '/project/new', dict(name='test project', description=''))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/1')

        # Fetch logout page
        response = self.get('/logout')
        self.assertEqual(response.code, 404)

    def test_project(self):
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
        response = self.get('/?token=' + self.application.single_user_token)
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/')

        # Check project list
        response = self.get('/')
        self.assertEqual(response.code, 200)
        self.assertIn(b"first project", response.body)
        self.assertIn(b"a test", response.body)
        self.assertNotIn(b"private P", response.body)
        self.assertIn(b"last project", response.body)


if __name__ == '__main__':
    unittest.main()
