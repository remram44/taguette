from tornado.testing import AsyncTestCase, gen_test
import unittest

from tagger import convert


class TestConvert(AsyncTestCase):
    @gen_test
    async def test_convert_txt(self):
        body = (
            b"\n  This is an example text document.\nIt should be converted. "
            b"\n\n  It has another paragraph here.\n  "
        )
        body = await convert.to_numbered_html(body, 'text/plain', 'test.txt')
        self.assertEqual(
            body,
            "<p id=\"doc-item-1\">This is an example text document.\nIt should be converted.</p>\n\n"
            "<p id=\"doc-item-2\">It has another paragraph here.</p>"
        )


if __name__ == '__main__':
    unittest.main()
