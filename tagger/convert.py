import html
import re


class ConversionError(ValueError):
    """Error converting document.
    """


_re_paragraph_break = re.compile('\n\n+')


def convert_file(body, content_type, filename):
    # TODO: Convert more document types to HTML
    if content_type == 'text/plain':
        body = body.decode('utf-8', 'replace')
        body = html.escape(body).strip()
        body = _re_paragraph_break.sub('</p>\n\n<p>', body)
        return '<p>%s</p>' % body
    else:
        raise ConversionError("Unknown file type %r" % content_type)
