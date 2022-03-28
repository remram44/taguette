import asyncio
import bleach
import bs4
import chardet
import codecs
import io
import jinja2
import logging
import opentelemetry.trace
import os
import pkg_resources
import prometheus_client
from prometheus_async.aio import time as prom_async_time
import shutil
import subprocess
from subprocess import CalledProcessError
import subtitle_parser
import sys
import tempfile
from xml.etree import ElementTree

from .utils import log_and_wait_proc


logger = logging.getLogger(__name__)
tracer = opentelemetry.trace.get_tracer(__name__)


BUCKETS = [1.0, 2.0, 3.0, 4.0, 5.0,
           6.0, 8.0, 10.0, 12.0, 15.0, 18.0,
           22.0, 26.0, 30.0, 36.0, 42.0, 48.0, 60.0, 90.0]
PROM_CALIBRE_TOHTML = prometheus_client.Counter(
    'convert_calibre_tohtml_total',
    "Conversions to HTML using Calibre (calibre_to_html())",
)
PROM_CALIBRE_TOHTML_TIME = prometheus_client.Histogram(
    'convert_calibre_tohtml_seconds',
    "Time to convert to HTML using Calibre (calibre_to_html())",
    buckets=BUCKETS,
)
PROM_WVWARE_TOHTML = prometheus_client.Counter(
    'convert_wvware_tohtml_total',
    "Conversions to HTML using wvHtml (wvware_to_html())",
)
PROM_WVWARE_TOHTML_TIME = prometheus_client.Histogram(
    'convert_wvware_tohtml_seconds',
    "Time to convert to HTML using wvHtml (wvware_to_html())",
)
PROM_CALIBRE_FROMHTML = prometheus_client.Counter(
    'convert_calibre_fromhtml_total',
    "Conversions from HTML using Calibre (calibre_from_html())",
    ['extension'],
)
PROM_CALIBRE_FROMHTML_TIME = prometheus_client.Histogram(
    'convert_calibre_fromhtml_seconds',
    "Time to convert from HTML using Calibre (calibre_from_html())",
    buckets=BUCKETS,
)
PROM_CONVERT_PROCESSES = prometheus_client.Gauge(
    'convert_processes',
    "Number of conversion processes currently running",
)
PROM_CONVERT_QUEUE = prometheus_client.Gauge(
    'convert_queue',
    "Number of conversions waiting to run",
)


HTML_EXTENSIONS = ('.htm', '.html', '.xhtml')


template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        [pkg_resources.resource_filename('taguette', 'templates')],
    ),
    autoescape=jinja2.select_autoescape(['html']),
)


def _render_string(template_name, **kwargs):
    template = template_env.get_template(template_name)
    return template.render(**kwargs)


class ConversionError(ValueError):
    """Error converting document.
    """


class UnsupportedFormat(ConversionError):
    """This format is not supported.
    """
    def __init__(self, msg="Unsupported file format",):
        super(UnsupportedFormat, self).__init__(msg)


PROC_TERM_GRACE = 5  # Wait 5s after SIGTERM before sending SIGKILL

PROC_MAX_CONCURRENT = 4  # Maximum concurrent conversion processes


class MeasuredSemaphore(asyncio.Semaphore):
    def __init__(self, value, metric_acquired, metric_waiting):
        super(MeasuredSemaphore, self).__init__(value)
        self._metric_acquired = metric_acquired
        self._metric_waiting = metric_waiting

    async def acquire(self):
        self._metric_waiting.inc()
        ret = await super(MeasuredSemaphore, self).acquire()
        self._metric_waiting.dec()
        self._metric_acquired.inc()
        return ret

    def release(self):
        super(MeasuredSemaphore, self).release()
        self._metric_acquired.dec()


subprocess_sem = MeasuredSemaphore(
    PROC_MAX_CONCURRENT,
    PROM_CONVERT_PROCESSES,
    PROM_CONVERT_QUEUE,
)


# Windows only supports subprocesses with the asyncio ProactorEventLoop
# However tornado only supports the SelectorEventLoop
# https://github.com/tornadoweb/tornado/issues/2608
# For now we can't use asyncio subprocesses on Windows
async def _check_call_threadpool(cmd, timeout, env=None):
    async with subprocess_sem:
        with tracer.start_as_current_span(
            'taguette/subprocess',
            attributes={'command': ' '.join(cmd)},
        ):
            return await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.check_call(cmd, timeout=timeout, env=env),
            )


async def _check_call_asyncio(cmd, timeout, env=None):
    async with subprocess_sem:
        with tracer.start_as_current_span(
            'taguette/subprocess',
            attributes={'command': ' '.join(cmd)},
        ):
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            try:
                retcode = await asyncio.wait_for(
                    log_and_wait_proc(logger, proc),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Process didn't finish before %ds timeout: %r",
                    timeout, cmd,
                )
                try:
                    proc.terminate()
                    try:
                        await asyncio.wait_for(proc.wait(), PROC_TERM_GRACE)
                    except asyncio.TimeoutError:
                        proc.kill()
                except ProcessLookupError:
                    pass
                raise asyncio.TimeoutError
            else:
                if retcode != 0:
                    raise CalledProcessError(retcode, cmd)


if sys.platform == 'win32':
    check_call = _check_call_threadpool
else:
    check_call = _check_call_asyncio


# Something to HTML


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
            e.replace_with(e.text)
            continue
        href = e.attrs['href'].lower()
        if not (href.startswith('http://') or
                href.startswith('https://') or
                href.startswith('mailto:')):
            e.attrs['title'] = e.attrs['href']
            del e.attrs['href']
        else:
            if 'title' in e.attrs:
                del e.attrs['title']
    # Back to string
    body = str(soup)
    del soup

    # Use bleach to sanitize the content
    body = bleach.clean(
        body,
        tags=['p', 'br', 'a', 'img',
              'h1', 'h2', 'h3', 'h4', 'h5',
              'strong', 'em', 'b', 'u',
              'ul', 'ol', 'li'],
        attributes={'a': ['href', 'title'], 'img': ['src']},
        strip=True,
    )

    body = body.strip()

    return body


def is_html_safe(text):
    """Check whether the given HTML is safe.

    For situation where we cannot run `get_html_body()`, this will throw out
    unsafe HTML.
    """
    if isinstance(text, bytes):
        try:
            text = text.decode('utf-8')
        except UnicodeDecodeError as e:
            logging.warning("is_html_safe(): %s", e)
            return False
    elif not isinstance(text, str):
        raise TypeError("is_html_safe() expects str or bytes, not %r" % (
            type(text).__name__,
        ))

    soup = bs4.BeautifulSoup(text, 'html5lib')
    # Check 'src' URLs
    for e in soup.find_all('img'):
        if e.attrs['src'] != '/static/missing.png':
            return False

    # Use bleach to sanitize the content
    cleaned = bleach.clean(
        text,
        tags=['p', 'br', 'a', 'img',
              'h1', 'h2', 'h3', 'h4', 'h5',
              'strong', 'em', 'b', 'u',
              'ul', 'ol', 'li'],
        attributes={'a': ['href', 'title'], 'img': ['src', 'width', 'height']},
        strip=True,
    )

    # text.strip() == cleaned.strip()
    # This doesn't work because bleach changed from outputting <br/> to <br>

    return (
        text.strip().replace('/>', '>')
        == cleaned.strip().replace('/>', '>')
    )


@tracer.start_as_current_span('taguette/convert/calibre_to_html')
@prom_async_time(PROM_CALIBRE_TOHTML_TIME)
async def calibre_to_html(input_filename, temp_dir, config):
    PROM_CALIBRE_TOHTML.inc()

    output_dir = os.path.join(temp_dir, 'output')
    output = []
    convert = 'ebook-convert'
    if os.environ.get('CALIBRE'):
        convert = os.path.join(os.environ['CALIBRE'], convert)
    cmd = [convert, input_filename, output_dir]
    if os.path.splitext(input_filename)[1].lower() == '.pdf':
        cmd.append('--no-images')
    cmd_heuristics = cmd + ['--enable-heuristics']
    logger.info("Running: %s", ' '.join(cmd_heuristics))
    try:
        try:
            await check_call(cmd_heuristics, config['CONVERT_TO_HTML_TIMEOUT'],
                             env=dict(os.environ, TMPDIR=temp_dir))
        except asyncio.TimeoutError:
            logger.warning("Calibre timed out, trying again without "
                           "heuristics...")
            try:
                await check_call(cmd, config['CONVERT_TO_HTML_TIMEOUT'],
                                 env=dict(os.environ, TMPDIR=temp_dir))
            except asyncio.TimeoutError:
                raise ConversionError("Calibre took too long and was stopped")
    except OSError:
        raise ConversionError("Calibre is not available")
    except CalledProcessError:
        raise ConversionError("Calibre couldn't convert that file")
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

    size = os.stat(os.path.join(output_dir, manifest)).st_size
    if size > config['OPF_OUT_SIZE_LIMIT']:
        logger.warning("OPF manifest is %d bytes; aborting", size)
        raise ConversionError("Output manifest is too long")

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
    size = 0
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
        size += os.stat(output_filename).st_size
        if size > config['HTML_OUT_SIZE_LIMIT']:
            logger.warning(
                "File is %d bytes for a total of %d bytes; aborting",
                os.stat(output_filename).st_size,
                size,
            )
            raise ConversionError("Output file is too long")
        with open(output_filename, 'rb') as fp:
            output.append(get_html_body(fp.read()))
    # TODO: Store media files

    # Assemble output
    return '\n'.join(output)


@tracer.start_as_current_span('taguette/convert/wvware_to_html')
@prom_async_time(PROM_WVWARE_TOHTML_TIME)
async def wvware_to_html(input_filename, tmp, config):
    PROM_WVWARE_TOHTML.inc()
    output_filename = os.path.join(tmp, 'output.html')

    # Run WV
    convert = 'wvHtml'
    if os.environ.get('WVHTML'):
        convert = os.environ['WVHTML']
    cmd = [convert, input_filename, output_filename]
    logger.info("Running: %s", ' '.join(cmd))
    try:
        await check_call(cmd, config['CONVERT_TO_HTML_TIMEOUT'])
    except OSError:
        raise ConversionError("Can't call wvHtml to convert Word 97 file")
    except CalledProcessError:
        raise ConversionError("wvHtml couldn't convert that file")
    except asyncio.TimeoutError:
        raise ConversionError("wvHtml took too long and was stopped")
    logger.info("wvHtml successful")

    # Read output
    with open(output_filename, 'rb') as fp:
        return get_html_body(fp.read())


HTML_MIMETYPES = {'text/html', 'application/xhtml+xml'}


async def to_html(body, content_type, filename, config):
    logger.info("Converting file %r, type %r", filename, content_type)

    ext = os.path.splitext(filename)[1].lower()
    if ext in HTML_EXTENSIONS:
        return get_html_body(body)
    elif not ext:
        raise ConversionError("This file doesn't have an extension!")
    elif ext == '.doc':
        # Convert file to HTML using WV
        tmp = tempfile.mkdtemp(prefix='taguette_wv_')
        try:
            # Write file to temporary directory
            input_filename = os.path.join(tmp, filename)
            with open(input_filename, 'wb') as fp:
                fp.write(body)

            # Run wvHtml
            return await wvware_to_html(input_filename, tmp, config)
        finally:
            shutil.rmtree(tmp)
    elif ext in ('.srt', '.vtt'):
        # Convert file to HTML using subtitle-parser

        # Pick the parser class
        if ext == '.vtt':
            parser_cls = subtitle_parser.WebVttParser
        else:
            parser_cls = subtitle_parser.SrtParser

        # Detect encoding
        charset = chardet.detect(body)['encoding'] or 'utf-8'
        file = io.BytesIO(body)
        file = codecs.getreader(charset)(file)

        # Parse subtitle file
        try:
            parser = parser_cls(file)
            parser.parse()
        except subtitle_parser.SubtitleError as e:
            raise ConversionError("Invalid subtitle file: %s" % (e,))

        # Turn the result into HTML
        output = io.StringIO()
        subtitle_parser.render_html(parser.subtitles, output)
        return output.getvalue()
    else:
        # Convert file to HTML using Calibre
        tmp = tempfile.mkdtemp(prefix='taguette_calibre_')
        try:
            # Write file to temporary directory
            input_filename = os.path.join(tmp, filename)
            with open(input_filename, 'wb') as fp:
                fp.write(body)

            # Run Calibre
            return await calibre_to_html(
                input_filename,
                tmp,
                config,
            )
        finally:
            shutil.rmtree(tmp)


async def to_html_chunks(body, content_type, filename, config):
    html = await to_html(body, content_type, filename, config)
    # TODO: Do chunks
    return html


# HTML to something


@tracer.start_as_current_span('taguette/convert/calibre_from_html')
@prom_async_time(PROM_CALIBRE_FROMHTML_TIME)
async def calibre_from_html(html, extension, config):
    PROM_CALIBRE_FROMHTML.labels(extension).inc()

    # Convert file using Calibre
    tmp = tempfile.mkdtemp(prefix='taguette_calibre_')
    try:
        input_filename = os.path.join(tmp, 'input.html')
        with open(input_filename, 'w', encoding='utf-8') as fp:
            fp.write(html)
        output_filename = os.path.join(tmp, 'output.%s' % extension)
        convert = 'ebook-convert'
        if os.environ.get('CALIBRE'):
            convert = os.path.join(os.environ['CALIBRE'], convert)
        cmd = [convert, input_filename, output_filename,
               '--page-breaks-before=/']
        logger.info("Running: %s", ' '.join(cmd))
        try:
            await check_call(cmd, config['CONVERT_FROM_HTML_TIMEOUT'],
                             env=dict(os.environ, TMPDIR=tmp))
        except OSError:
            raise ConversionError("Calibre is not available")
        except CalledProcessError:
            raise ConversionError("Calibre couldn't convert that file")
        except asyncio.TimeoutError:
            raise ConversionError("Calibre took too long and was stopped")
        logger.info("ebook-convert successful")
        if not os.path.isfile(output_filename):
            raise RuntimeError("Output file does not exist")
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


def html_to_html(html, config):
    _ = config
    future = asyncio.get_event_loop().create_future()
    future.set_result([html])
    return future


html_to_extensions = {
    'html': (html_to_html,
             'text/html; charset=utf-8'),
    'doc': (lambda html, config: calibre_from_html(html, 'docx', config),
            'application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document; charset=utf-8'),
    'docx': (lambda html, config: calibre_from_html(html, 'docx', config),
             'application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.document; charset=utf-8'),
    'pdf': (lambda html, config: calibre_from_html(html, 'pdf', config),
            'application/pdf'),
    'rtf': (lambda html, config: calibre_from_html(html, 'rtf', config),
            'application/rtf'),
}
for n in html_to_extensions:
    PROM_CALIBRE_FROMHTML.labels(n).inc(0)


def html_to(html, extension, config):
    try:
        func, mimetype = html_to_extensions[extension.lower()]
    except KeyError:
        raise UnsupportedFormat
    return mimetype, asyncio.ensure_future(func(html, config))


def html_to_plaintext(html):
    soup = bs4.BeautifulSoup(html, 'html5lib')
    return soup.get_text(' ', strip=True)
