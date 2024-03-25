import asyncio
import logging
import os
import re
import sentry_sdk
import sys


logger = logging.getLogger(__name__)


def _f(message):
    """Pass-through translation function.

    Marks a string for translation without translating it at run time.
    """
    return message


class DefaultMap(object):
    def __init__(self, default, mapping):
        self.__default = default
        self.mapping = mapping

    def get(self, key):
        try:
            return self.mapping[key]
        except KeyError:
            return self.__default(key)

    def __getitem__(self, key):
        return self.get(key)


async def log_and_wait_proc(logger, proc):
    while proc.returncode is None:
        line = await proc.stdout.readline()
        if not line:
            break
        line = line.decode('utf-8', 'replace')
        if line[-1] == '\n':
            line = line[:-1]
        logger.info("%d: %s", proc.pid, line)

    ret = await proc.wait()
    lines = await proc.stdout.read()
    for line in lines.splitlines():
        line = line.decode('utf-8', 'replace')
        logger.info("%d: %s", proc.pid, line)
    return ret


_windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                         'LPT2', 'LPT3', 'PRN', 'NUL')
_not_ascii_re = re.compile(r'[^A-Za-z0-9_.-]')
_percent_escapes_re = re.compile(r'%[0-9A-Fa-f]{2}')


def sanitize_filename(name):
    """Sanitize a filename.

    This takes a filename, for example provided by a browser with a file
    upload, and turn it into something that is safe for opening.

    Adapted from werkzeug's secure_filename(), copyright 2007 the Pallets team.
    https://palletsprojects.com/p/werkzeug/
    """
    if not isinstance(name, str):
        raise ValueError("File name is not a string")
    if not name:
        raise ValueError("File name cannot be empty")
    name = _percent_escapes_re.sub('_', name)
    if '/' in name:
        name = name[name.rindex('/') + 1:]
    if sanitize_filename.windows and '\\' in name:
        # It seems that IE gets that wrong, at least when the file is from
        # a network share
        name = name[name.rindex('\\') + 1:]
    name, ext = os.path.splitext(name)
    name = name[:20]
    ext = ext[:8]
    name = _not_ascii_re.sub('', name).strip('._')
    if not name:
        name = '_'
    ext = _not_ascii_re.sub('', ext)
    if (
        sanitize_filename.windows
        and name.split('.')[0].upper() in _windows_device_files
    ):
        name = '_' + name
    name = name + ext
    return name


sanitize_filename.windows = os.name == 'nt'


_background_future_references = {}


def background_task(task, *, should_never_exit=False):
    future = asyncio.get_event_loop().create_task(task)
    ident = id(future)

    def callback(future):
        _background_future_references.pop(ident, None)
        try:
            future.result()
        except Exception as e:
            sentry_sdk.capture_exception(e)
            logger.exception("Exception in background task")
        if should_never_exit:
            logger.critical("Critical task died, exiting")
            asyncio.get_event_loop().stop()
            sys.exit(1)

    future.add_done_callback(callback)

    # Keep a strong reference to the future
    # https://bugs.python.org/issue21163
    _background_future_references[ident] = future
