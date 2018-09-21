from tornado.testing import AsyncTestCase, gen_test
import unittest
from unittest import mock

from tagger import convert


class TestConvert(AsyncTestCase):
    @gen_test
    async def test_convert_html(self):
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


if __name__ == '__main__':
    unittest.main()
