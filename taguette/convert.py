import asyncio
import bleach
import bs4
import logging
import os
import signal
import shutil
import tempfile
from xml.etree import ElementTree


logger = logging.getLogger(__name__)


HTML_EXTENSIONS = ('.htm', '.html', '.xhtml')


class ConversionError(ValueError):
    """Error converting document.
    """


if hasattr(signal, 'SIGCHLD'):
    from tornado.process import Subprocess, CalledProcessError

    def check_call(cmd):
        proc = Subprocess(cmd)
        return proc.wait_for_exit()
else:
    import subprocess
    from subprocess import CalledProcessError

    # Windows doesn't have this, so tornado.process doesn't work
    # Use Popen with a thread pool
    def check_call(cmd):
        return asyncio.get_event_loop().run_in_executor(
            None,
            subprocess.check_call,
            cmd
        )


def get_html_body(body):
    # Use beautifulsoup to remove head, script, style elements
    # (bleach can do that, but would keep the text inside them)
    soup = bs4.BeautifulSoup(body, 'html5lib')
    for tag in ['head', 'script', 'style']:
        for e in soup.find_all(tag):
            e.extract()
    # Update 'src' URLs
    for e in soup.find_all('img'):
        e.attrs['src'] = '/static/missing.png'
    # Update 'href' URLs
    for e in soup.find_all('a'):
        if 'href' not in e.attrs:
            continue
        href = e.attrs['href'].lower()
        if not href.startswith('http://') and not href.startswith('https://'):
            e.attrs['href'] = '#'
    # Back to string
    body = str(soup)
    del soup

    # Use bleach to sanitize the content
    body = bleach.clean(
        body,
        tags=['p', 'a', 'img',
              'h1', 'h2', 'h3', 'h4', 'h5',
              'strong', 'em', 'b', 'u',
              'ul', 'ol', 'li'],
        attributes={'a': ['href'], 'img': ['src', 'width', 'height']},
        strip=True,
    )

    body = body.strip()

    return body


HTML_MIMETYPES = {'text/html', 'application/xhtml+xml'}


async def to_html(body, content_type, filename):
    logger.info("Converting file %r, type %r", filename, content_type)

    if os.path.splitext(filename)[1].lower() in HTML_EXTENSIONS:
        return get_html_body(body)
    else:
        # Convert file to HTML using Calibre
        tmp = tempfile.mkdtemp(prefix='taguette_calibre_')
        output = []
        try:
            # Write file to temporary directory
            input_filename = os.path.join(tmp, filename)
            with open(input_filename, 'wb') as fp:
                fp.write(body)

            # Run Calibre
            output_dir = os.path.join(tmp, 'output')
            convert = 'ebook-convert'
            if os.environ.get('CALIBRE'):
                convert = os.path.join(os.environ['CALIBRE'], convert)
            cmd = [convert, input_filename, output_dir, '--enable-heuristics']
            logger.info("Running: %s", ' '.join(cmd))
            try:
                await check_call(cmd)
            except CalledProcessError as e:
                raise ConversionError("Calibre returned %d" % e.returncode)
            logger.info("ebook-convert successful")

            # Locate OEB manifest
            manifests = [e.lower() for e in os.listdir(output_dir)]
            manifests = [e for e in manifests if e.endswith('.opf')]
            if not manifests:
                logger.error("No OPF manifest in Calibre's output")
                raise ConversionError("Invalid output from Calibre")
            elif manifests == ['content.opf']:
                manifest = 'content.opf'  # All good
            elif len(manifests) > 1 and 'content.opf' in manifests:
                logger.warning("Calibre's output contains multiple OPF "
                               "manifests! Using content.opf")
                manifest = 'content.opf'
            elif len(manifests) == 1 and manifests[0] != 'content.opf':
                manifest, = manifests
                logger.warning("Unusual name for OPF manifest in Calibre's "
                               "output: %r", manifest)
            else:
                logger.error("Multiple OPF manifests in Calibre's output: "
                             "%r" % manifests)
                raise ConversionError("Invalid output from Calibre")

            # Open OEB manifest
            logger.info("Parsing OPF manifest %s", manifest)
            tree = ElementTree.parse(os.path.join(output_dir, manifest))
            root = tree.getroot()
            ns = '{http://www.idpf.org/2007/opf}'
            if root.tag not in ('package', ns + 'package'):
                logger.error("Invalid root tag in OPF manifest: %r", root.tag)
                raise ConversionError("Invalid output from Calibre")
            manifests = [tag for tag in root
                         if tag.tag in ('manifest', ns + 'manifest')]
            if len(manifests) != 1:
                logger.error("OPF has %d <manifest> nodes", len(manifests))
                raise ConversionError("Invalid output from Calibre")
            manifest, = manifests
            spines = [tag for tag in root
                      if tag.tag in ('spine', ns + 'spine')]
            if len(spines) != 1:
                logger.error("OPF has %d <spine> nodes", len(spines))
                raise ConversionError("Invalid output from Calibre")
            spine, = spines

            # Read <manifest>
            items = {}
            for item in manifest:
                if item.tag not in ('item', ns + 'item'):
                    continue
                try:
                    name = item.attrib['href']
                    mimetype = item.attrib['media-type']
                    id_ = item.attrib['id']
                except KeyError:
                    logger.error("Missing attributes from <item> in OPF "
                                 "manifest. Present: %s",
                                 ', '.join(item.attrib))
                    raise ConversionError("Invalid output from Calibre")
                else:
                    items[id_] = name, mimetype
            logger.info("Read %d items", len(items))

            # Read <spine>
            for item in spine:
                if item.tag not in ('itemref', ns + 'itemref'):
                    continue
                try:
                    idref = item.attrib['idref']
                except KeyError:
                    logger.error("Missing attribute 'idref' from <itemref> in "
                                 "OPF manifest. Present: %s",
                                 ', '.join(item.attrib))
                    raise ConversionError("Invalid output from Calibre")
                try:
                    output_name, output_mimetype = items[idref]
                except KeyError:
                    logger.error("Spine entry references missing item %r",
                                 idref)
                    raise ConversionError("Invalid output from Calibre")
                if output_mimetype not in HTML_MIMETYPES:
                    logger.warning("Ignoring item %r, mimetype=%r",
                                   idref, output_mimetype)
                    continue
                output_filename = os.path.join(output_dir, output_name)
                if not os.path.isfile(output_filename):
                    logger.error("Missing file from output dir: %r",
                                 output_name)
                    raise ConversionError("Invalid output from Calibre")

                # Read output
                logger.info("Reading in %r", output_name)
                with open(output_filename, 'rb') as fp:
                    output.append(get_html_body(fp.read()))
            # TODO: Store media files

            # Assemble output
            return '\n'.join(output)
        finally:
            shutil.rmtree(tmp)


async def to_html_chunks(body, content_type, filename):
    html = await to_html(body, content_type, filename)
    # TODO: Do chunks
    return html


async def calibre_from_html(html, extension):
    # Convert file using Calibre
    tmp = tempfile.mkdtemp(prefix='taguette_calibre_')
    try:
        input_filename = os.path.join(tmp, 'input.html')
        with open(input_filename, 'w') as fp:
            fp.write(html)
        output_filename = os.path.join(tmp, 'output.%s' % extension)
        convert = 'ebook-convert'
        if os.environ.get('CALIBRE'):
            convert = os.path.join(os.environ['CALIBRE'], convert)
        cmd = [convert, input_filename, output_filename,
               '--page-breaks-before=/']
        logger.info("Running: %s", ' '.join(cmd))
        try:
            await check_call(cmd)
        except CalledProcessError as e:
            raise ConversionError("Calibre returned %d" % e.returncode)
        logger.info("ebook-convert successful")
        if not os.path.isfile(output_filename):
            raise RuntimeError("output file does not exist")
    except Exception:
        shutil.rmtree(tmp)
        raise
    else:
        def reader():
            try:
                with open(output_filename, 'rb') as fp:
                    chunk = fp.read(4096)
                    yield chunk
                    while len(chunk) == 4096:
                        chunk = fp.read(4096)
                        if chunk:
                            yield chunk
            finally:
                shutil.rmtree(tmp)

        return reader()


def html_to_html(html):
    future = asyncio.get_event_loop().create_future()
    future.set_result([html])
    return future


_extensions = {
    'html': (html_to_html,
             'text/html; charset=utf-8'),
    'doc': (lambda html: calibre_from_html(html, 'docx'),
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document; charset=utf-8'),
    'docx': (lambda html: calibre_from_html(html, 'docx'),
             'application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.document; charset=utf-8'),
    'pdf': (lambda html: calibre_from_html(html, 'pdf'),
            'application/pdf'),
}


def html_to(html, extension):
    func, mimetype = _extensions[extension]
    return mimetype, asyncio.ensure_future(func(html))
