from tornado.testing import AsyncTestCase, gen_test
import unittest
from unittest import mock

from taguette import convert, web


class TestConvert(AsyncTestCase):
    @gen_test
    async def test_convert_html(self):
        """Tests converting HTML, using BeautifulSoup and Bleach"""
        body = (
            b"<!DOCTYPE html>\n"
            b"<html>\n  <head>\n  <title>Test</title>\n</head>\n<body>"
            b"<h1>Example</h1><p>This is an example text document.\n"
            b"It should be <blink>converted</blink>.</p>\n\n"
            b"<p>It has another paragraph <strong>here</strong>.</p>\n"
            b"</body></html>\n"
        )
        with mock.patch('tornado.process.Subprocess', object()):
            body = await convert.to_html(body, 'text/html', 'test.html')
        self.assertEqual(
            body,
            "<h1>Example</h1><p>This is an example text document.\n"
            "It should be converted.</p>\n\n"
            "<p>It has another paragraph <strong>here</strong>.</p>"
        )


class TestMeasure(unittest.TestCase):
    def setUp(self):
        import logging
        logging.basicConfig(level=logging.INFO)

    def test_find_tags(self):
        """Tests finding tags in a string."""
        html = '<p><img />  here\'s a <a checked href="value" >link< /a></p>'
        html = html.encode('utf-8')
        self.assertEqual(
            [((m.start(), m.end()), m.groups())
             for m in web._re_tags.finditer(html)],
            [
                ((0, 3), (b'', b'p')),
                ((3, 10), (b'', b'img')),
                ((21, 46), (b'', b'a')),
                ((50, 55), (b'/', b'a')),
                ((55, 59), (b'/', b'p')),
            ]
        )

    def test_extract_highlight(self):
        """Tests locating a highlight in an HTML document."""
        html = '<p><img />  here\'s a <a checked href="value" >link< /a></p>'
        snippet = web.HighlightAdd.extract_highlight(html, 4, 13)
        self.assertEqual(snippet,
                         b'<p>re\'s a <a check href="value" >li</a></p>')


if __name__ == '__main__':
    unittest.main()
