from http.cookies import SimpleCookie
import re
from tornado.gen import sleep
from tornado.testing import AsyncTestCase, gen_test, AsyncHTTPTestCase, \
    get_async_test_timeout
import unittest
from unittest import mock
from urllib.parse import urlencode

from taguette import convert, database, extract, web


class TestConvert(AsyncTestCase):
    @gen_test
    async def test_convert_html(self):
        """Tests converting HTML, using BeautifulSoup and Bleach"""
        body = (
            b"<!DOCTYPE html>\n"
            b"<html>\n  <head>\n  <title>Test</title>\n</head>\n<body>"
            b"<h1>Example</h1><p>This is an example text document.\n"
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
            body = await convert.to_html(body, 'text/html', 'test.html')
        self.assertEqual(
            body,
            "<h1>Example</h1><p>This is an example text document.\n"
            "It should be converted.</p>\n\n"
            "<p>It has another paragraph <strong>here</strong>, "
            "images: <img src=\"/static/missing.png\" width=\"50\"> "
            "<img src=\"/static/missing.png\" width=\"30\"> "
            "<img src=\"/static/missing.png\">, and "
            "links: <a href=\"#\">1</a> "
            "<a href=\"#\">2</a> "
            "<a href=\"http://and/the/last/one\">3</a></p>"
        )


class TestMergeOverlapping(unittest.TestCase):
    def test_merge_overlapping_ranges(self):
        """Tests merging overlapping ranges."""
        self.assertEqual(web.merge_overlapping_ranges([]), [])
        self.assertEqual(web.merge_overlapping_ranges([(1, 3)]), [(1, 3)])
        self.assertEqual(web.merge_overlapping_ranges([(1, 2), (3, 4)]),
                         [(1, 2), (3, 4)])
        self.assertEqual(
            web.merge_overlapping_ranges([
                (1, 3),
                (12, 14),
                (5, 7),
                (10, 12),
                (2, 6),
                (23, 25),
                (17, 21),
                (18, 20),
            ]), [
                (1, 7),
                (10, 14),
                (17, 21),
                (23, 25),
            ]
        )


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
        """Tests highlighting an HTML document."""
        html = '<p><u>Hello</u> there <i>World</i></p>'
        self.assertEqual(
            extract.highlight(html, [(0, 1), (2, 3),
                                     (4, 8), (10, 14), (15, 17)])
            .replace('<span class="highlight">', '{')
            .replace('</span>', '}'),
            '<p><u>{H}e{l}l{o}</u>{ th}er{e }<i>{Wo}r{ld}</i></p>',
        )


class MyHTTPTestCase(AsyncHTTPTestCase):
    xsrf = None

    def setUp(self):
        web.Application.check_messages = lambda *a: None
        super(MyHTTPTestCase, self).setUp()
        self.cookie = SimpleCookie()

    _re_xsrf = re.compile(
        br'<input type="hidden" name="_xsrf" value="([^">]+)" */?>')

    def update(self, response):
        if response.code < 400:
            m = self._re_xsrf.search(response.body)
            if m is not None:
                self.xsrf = m.group(1)
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

    async def apost(self, url, args):
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        headers['Cookie'] = self.get_cookie()
        response = self._fetch(url, method='POST', follow_redirects=False,
                               headers=headers,
                               body=urlencode(dict(args, _xsrf=self.xsrf)))
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
            self.application = web.make_app('sqlite://', True)
            return self.application

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

        # Fetch registration page
        response = self.get('/register')
        self.assertEqual(response.code, 200)

        # Register
        response = self.post(
            '/register', dict(login='tester',
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

        # Fetch login page
        response = self.get('/login?' + urlencode(dict(next='/project/1')))
        self.assertEqual(response.code, 200)

        # Log in
        response = self.post('/login',
                             dict(next='/project/1', login='admin',
                                  password='hackme'))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/1')

    @gen_test
    async def test_projects(self):
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
        init_js = '\n'.join(body[idx:].splitlines()[2:6])
        self.assertEqual(init_js,
                         '  var project_id = 1;\n'
                         '  var last_event = -1;\n'
                         '  var documents = {};\n'
                         '  var tags = {"1": {"description": "Further review '
                         'required", "id": 1, "path": "interesting"}, '
                         '"2": {"description": "Known people", "id": 2, '
                         '"path": "people"}};')

        # Start polling
        poll_proj1 = self.poll_event(1, -1)

        # Create project 2
        response = await self.aget('/project/new')
        self.assertEqual(response.code, 200)
        response = await self.apost('/project/new', dict(name='other project',
                                                         description=''))
        self.assertEqual(response.code, 302)
        self.assertEqual(response.headers['Location'], '/project/2')

        # Start polling
        poll_proj2 = self.poll_event(2, -1)

        # Create tags in project 2
        # Create document 1 in project 1
        # Create document 2 in project 2
        # Create highlight 1 in document 1
        # Change project 2 metadata
        # Create document 3 in project 2
        # Create highlight 2 in document 2
        # Create highlight 3 in document 2
        # List highlights in project 2

    async def poll_event(self, proj, from_id):
        response = await self.aget('/api/project/%d/events?from=%d' % (
                                   proj, from_id))
        self.assertEqual(response.code, 200)
        return json.loads(response.body.decode('utf-8'))


class TestSingleuser(MyHTTPTestCase):
    def get_app(self):
        with mock.patch.object(web.Application, '_set_password',
                               new=set_dumb_password):
            self.application = web.make_app('sqlite://', False)
            return self.application

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
        self.assertEqual(response.code, 403)

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
