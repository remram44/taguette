import html
import re


class ConversionError(ValueError):
    """Error converting document.
    """


_re_paragraph_break = re.compile(r'(?:\s*\n){2,}\s*')


def to_paragraphs(body, content_type, filename):
    # TODO: Convert more document types
    if content_type == 'text/plain':
        body = body.decode('utf-8', 'replace')
        body = html.escape(body).strip()
        return _re_paragraph_break.split(body)
    else:
        raise ConversionError("Unknown file type %r" % content_type)


def to_numbered_html(body, content_type, filename):
    paragraphs = to_paragraphs(body, content_type, filename)
    return '\n\n'.join('<p id="doc-item-%d">%s</p>' % (i + 1, p)
                       for i, p in enumerate(paragraphs))
