import bleach
import bs4
import logging
import os
import shutil
import tempfile
from tornado.process import Subprocess, CalledProcessError


logger = logging.getLogger(__name__)


HTML_EXTENSIONS = ('.htm', '.html', '.xhtml')


class ConversionError(ValueError):
    """Error converting document.
    """


async def to_html(body, content_type, filename):
    logger.info("Converting file %r, type %r", filename, content_type)

    if os.path.splitext(filename)[1].lower() not in HTML_EXTENSIONS:
        # Convert file to HTML using Calibre
        tmp = tempfile.mkdtemp(prefix='tagger_calibre_')
        try:
            input_filename = os.path.join(tmp, filename)
            with open(input_filename, 'wb') as fp:
                fp.write(body)
            output_dir = os.path.join(tmp, 'output')
            cmd = ['ebook-convert', input_filename, output_dir]
            logger.info("Running: %s", ' '.join(cmd))
            proc = Subprocess(cmd)
            try:
                await proc.wait_for_exit()
            except CalledProcessError as e:
                raise ConversionError("Calibre returned %d" % e.returncode)
            logger.info("ebook-convert successful")
            output_filename = os.path.join(output_dir, 'index.html')
            with open(output_filename, 'rb') as fp:
                body = fp.read()
            # TODO: Store media files
        finally:
            shutil.rmtree(tmp)

    # Use beautifulsoup to remove head, script, style elements
    # (bleach can do that, but would keep the text inside them)
    soup = bs4.BeautifulSoup(body, 'html5lib')
    for tag in ['head', 'script', 'style']:
        for e in soup.find_all(tag):
            e.extract()
    # Update 'src' URLs
    for e in soup.find_all('img'):
        e.attrs['src'] = '/static/missing.png'
    body = str(soup)
    del soup

    # Use bleach to sanitize the content
    body = bleach.clean(
        body,
        tags=['p', 'a', 'img',
              'h1', 'h2', 'h3', 'h4', 'h5',
              'strong', 'em', 'b', 'u'],
        attributes={'a': ['href'], 'img': ['src']},
        strip=True,
    )

    body = body.strip()

    return body


async def to_html_chunks(body, content_type, filename):
    html = await to_html(body, content_type, filename)
    # TODO: Do chunks
    return html
