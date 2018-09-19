import html
import logging
import mimetypes
import os
import re
import shutil
import tempfile
from tornado.process import Subprocess, CalledProcessError


logger = logging.getLogger(__name__)


class ConversionError(ValueError):
    """Error converting document.
    """


_re_paragraph_break = re.compile(r'(?:\s*\n){2,}\s*')


def _plaintext_to_paragraphs(body):
    body = body.decode('utf-8', 'replace')
    body = html.escape(body).strip()
    return _re_paragraph_break.split(body)


async def to_paragraphs(body, content_type, filename):
    # Use extension, browser might not understand type
    if filename and '.' in filename:
        guessed_type = mimetypes.guess_type(filename)[0]
        if guessed_type:
            content_type = guessed_type

    logger.info("Converting file %r, type %r", filename, content_type)

    if content_type == 'text/plain':
        pass  # No conversion needed
    else:
        # Try Calibre
        body = await _calibre(body, 'input.pdf')

    return _plaintext_to_paragraphs(body)


async def to_numbered_html(body, content_type, filename):
    paragraphs = await to_paragraphs(body, content_type, filename)
    return '\n\n'.join('<p id="doc-item-%d">%s</p>' % (i + 1, p)
                       for i, p in enumerate(paragraphs))


async def _calibre(body, filename):
    tmp = tempfile.mkdtemp(prefix='tagger_calibre_')
    try:
        input_filename = os.path.join(tmp, filename)
        with open(input_filename, 'wb') as fp:
            fp.write(body)
        output_filename = os.path.join(tmp, 'output.txt')
        logger.info("Running ebook-convert")
        proc = Subprocess(['ebook-convert',
                           input_filename, output_filename,
                           #'--txt-output-formatting=markdown', '--keep-links',
                           '--newline=unix'])
        try:
            await proc.wait_for_exit()
        except CalledProcessError as e:
            raise ConversionError("Calibre returned %d" % e.returncode)
        logger.info("ebook-convert successful")
        with open(output_filename, 'rb') as fp:
            return fp.read()
    finally:
        shutil.rmtree(tmp)
