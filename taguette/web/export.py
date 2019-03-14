import bisect
import csv
import io
import logging
from markupsafe import Markup
import prometheus_client
from sqlalchemy.orm import aliased, joinedload
from tornado.web import authenticated

from .. import convert
from .. import database
from .. import extract
from .base import BaseHandler


logger = logging.getLogger(__name__)


PROM_EXPORT = prometheus_client.Counter(
    'export_total',
    "Export",
    ['what', 'extension'],
)


def init_PROM_EXPORT(w):
    for e in convert.html_to_extensions:
        PROM_EXPORT.labels(w, e).inc(0)


def export_doc(wrapped):
    async def wrapper(self, *args):
        ext = args[-1]
        ext = ext.lower()
        name, html = wrapped(self, *args)
        mimetype, contents = convert.html_to(html, ext)
        self.set_header('Content-Type', mimetype)
        self.set_header('Content-Disposition',
                        'attachment; filename="%s.%s"' % (name, ext))
        for chunk in await contents:
            self.write(chunk)
        self.finish()
    return wrapper


class ExportHighlightsDoc(BaseHandler):
    init_PROM_EXPORT('highlights_doc')

    @authenticated
    @export_doc
    def get(self, project_id, path, ext):
        PROM_EXPORT.labels('highlights_doc', ext.lower()).inc()
        project, _ = self.get_project(project_id)

        if path:
            tag = aliased(database.Tag)
            hltag = aliased(database.HighlightTag)
            highlights = (
                self.db.query(database.Highlight)
                .options(joinedload(database.Highlight.document))
                .join(hltag, hltag.highlight_id == database.Highlight.id)
                .join(tag, hltag.tag_id == tag.id)
                .filter(tag.path.startswith(path))
                .filter(tag.project == project)
            ).all()
        else:
            # Special case to select all highlights: we also need to select
            # highlights that have no tag at all
            document = aliased(database.Document)
            highlights = (
                self.db.query(database.Highlight)
                .join(document, document.id == database.Highlight.document_id)
                .filter(document.project == project)
            ).all()

        html = self.render_string('export_highlights.html', path=path,
                                  highlights=highlights)
        return 'path', html


def merge_overlapping_ranges(ranges):
    """Merge overlapping ranges in a sequence.
    """
    ranges = iter(ranges)
    try:
        merged = [next(ranges)]
    except StopIteration:
        return []

    for rg in ranges:
        left = right = bisect.bisect_right(merged, rg)
        # Merge left
        while left >= 1 and rg[0] <= merged[left - 1][1]:
            rg = (min(rg[0], merged[left - 1][0]),
                  max(rg[1], merged[left - 1][1]))
            left -= 1
        # Merge right
        while (right < len(merged) and
               merged[right][0] <= rg[1]):
            rg = (min(rg[0], merged[right][0]),
                  max(rg[1], merged[right][1]))
            right += 1
        # Insert
        if left == right:
            merged.insert(left, rg)
        else:
            merged[left:right] = [rg]

    return merged


class ExportDocument(BaseHandler):
    init_PROM_EXPORT('document')

    @authenticated
    @export_doc
    def get(self, project_id, document_id, ext):
        PROM_EXPORT.labels('document', ext.lower()).inc()
        doc, _ = self.get_document(project_id, document_id, True)

        highlights = merge_overlapping_ranges((hl.start_offset, hl.end_offset)
                                              for hl in doc.highlights)

        html = self.render_string(
            'export_document.html',
            name=doc.name,
            contents=Markup(extract.highlight(doc.contents, highlights)),
        )
        return doc.name, html


class ExportCodebookCsv(BaseHandler):
    PROM_EXPORT.labels('codebook', 'csv').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'csv').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.csv"')
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['tag', 'description'])
        for tag in tags:
            writer.writerow([tag.path, tag.description])
        self.finish(buf.getvalue())


class ExportCodebookDoc(BaseHandler):
    init_PROM_EXPORT('codebook')

    @authenticated
    @export_doc
    def get(self, project_id, ext):
        PROM_EXPORT.labels('codebook', ext.lower()).inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        html = self.render_string('export_codebook.html', tags=tags)
        return 'codebook', html
