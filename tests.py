from tornado.testing import AsyncTestCase, gen_test
import unittest
from unittest import mock

from taguette import convert, extract


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


class TestMeasure(unittest.TestCase):
    def test_extract_highlight(self):
        """Tests extracting a highlight from an HTML document."""
        html = '<p><u>Hello</u> there <i>World</i></p>'
        snippet = extract.extract(html, 7, 14)
        self.assertEqual(snippet,
                         '<p>here <i>Wo</i></p>')


if __name__ == '__main__':
    unittest.main()
