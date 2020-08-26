import asyncio
import csv
import logging
from markupsafe import Markup
import os
import prometheus_client
import shutil
from sqlalchemy.orm import aliased, joinedload
import tempfile
from tornado.web import authenticated
from xml.sax.saxutils import XMLGenerator
import xlsxwriter

from .. import convert
from .. import database
from .. import extract
from .. import refi_qda
from .base import BaseHandler

logger = logging.getLogger(__name__)


class WriteAdapter(object):
    def __init__(self, write_func):
        self.write = write_func

    def flush(self):
        pass


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

        # Call wrapped function to get document
        ret = wrapped(self, *args)
        if asyncio.isfuture(ret) or asyncio.iscoroutine(ret):
            name, html = await ret
        else:
            name, html = ret

        # Convert using Calibre
        try:
            mimetype, contents = convert.html_to(
                html, ext,
                self.application.config,
            )
        except convert.UnsupportedFormat:
            self.set_status(404)
            self.set_header('Content-Type', 'text/plain')
            return self.finish("Unsupported format: %s" % ext)

        # Return document
        self.set_header('Content-Type', mimetype)
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.%s"' % (name, ext))
        else:
            self.set_header('Content-Disposition', 'attachment')
        for chunk in await contents:
            self.write(chunk)
        return self.finish()

    return wrapper


class BaseExportHighlights(BaseHandler):
    def get_highlights_for_export(self, project_id, path):
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
                .order_by(database.Highlight.document_id,
                          database.Highlight.start_offset)
            ).all()
            name = None
        else:
            # Special case to select all highlights: we also need to select
            # highlights that have no tag at all
            document = aliased(database.Document)
            highlights = (
                self.db.query(database.Highlight)
                .join(document, document.id == database.Highlight.document_id)
                .filter(document.project == project)
                .order_by(database.Highlight.document_id,
                          database.Highlight.start_offset)
            ).all()
            name = 'all_tags'

        return name, highlights


class ExportHighlightsCsv(BaseExportHighlights):
    PROM_EXPORT.labels('highlights_doc', 'csv').inc(0)

    @authenticated
    def get(self, project_id, path):
        PROM_EXPORT.labels('highlights_doc', 'csv').inc()

        name, highlights = self.get_highlights_for_export(project_id, path)

        self.set_header('Content-Type', 'text/csv; charset=utf-8')
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.csv"' % name)
        else:
            self.set_header('Content-Disposition', 'attachment')
        writer = csv.writer(WriteAdapter(self.write))
        writer.writerow(['id', 'document', 'tag', 'content'])
        for hl in highlights:
            tags = hl.tags
            assert all(isinstance(t, database.Tag) for t in tags)
            if tags:
                tags = [t.path for t in tags]
            else:
                tags = ['']
            for tag_path in tags:
                writer.writerow([
                    hl.id, hl.document.name, tag_path,
                    convert.html_to_plaintext(hl.snippet),
                ])
        return self.finish()


class ExportHighlightsXlsx(BaseExportHighlights):
    PROM_EXPORT.labels('highlights_doc', 'xls').inc(0)

    @authenticated
    def get(self, project_id, path):
        PROM_EXPORT.labels('highlights_doc', 'xls').inc()

        name, highlights = self.get_highlights_for_export(project_id, path)

        self.set_header('Content-Type',
                        ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'))
        if name:
            self.set_header('Content-Disposition',
                            'attachment; filename="%s.xlsx"' % name)
        else:
            self.set_header('Content-Disposition', 'attachment')
        tmp = tempfile.mkdtemp(prefix='taguette_xlsx_')
        try:
            filename = os.path.join(tmp, 'highlights.xlsx')
            workbook = xlsxwriter.Workbook(filename)
            sheet = workbook.add_worksheet('highlights')

            header = workbook.add_format({'bold': True})

            sheet.write(0, 0, 'id', header)
            sheet.write(0, 1, 'document', header)
            sheet.write(0, 2, 'tag', header)
            sheet.write(0, 3, 'content', header)
            sheet.set_column(0, 0, 5.0)
            sheet.set_column(1, 1, 15.0)
            sheet.set_column(2, 2, 15.0)
            sheet.set_column(3, 3, 80.0)
            row = 1
            for hl in highlights:
                tags = hl.tags
                assert all(isinstance(t, database.Tag) for t in tags)
                if tags:
                    tags = [t.path for t in tags]
                else:
                    tags = ['']
                for tag_path in tags:
                    sheet.write(row, 0, str(hl.id))
                    sheet.write(row, 1, hl.document.name)
                    sheet.write(row, 2, tag_path)
                    sheet.write(row, 3, convert.html_to_plaintext(hl.snippet))
                    row += 1
            workbook.close()
            with open(filename, 'rb') as fp:
                chunk = fp.read(4096)
                self.write(chunk)
                while len(chunk) == 4096:
                    chunk = fp.read(4096)
                    if chunk:
                        self.write(chunk)
            return self.finish()
        finally:
            shutil.rmtree(tmp)


class ExportHighlightsDoc(BaseExportHighlights):
    init_PROM_EXPORT('highlights_doc')

    @authenticated
    @export_doc
    def get(self, project_id, path, ext):
        PROM_EXPORT.labels('highlights_doc', ext.lower()).inc()

        name, highlights = self.get_highlights_for_export(project_id, path)

        html = self.render_string('export_highlights.html', path=path,
                                  highlights=highlights)
        return name, html


class ExportDocument(BaseHandler):
    init_PROM_EXPORT('document')

    @authenticated
    @export_doc
    async def get(self, project_id, document_id, ext):
        PROM_EXPORT.labels('document', ext.lower()).inc()
        doc, _ = self.get_document(project_id, document_id, True)

        highlights = (
            self.db.query(database.Highlight)
            .filter(database.Highlight.document_id == document_id)
            .order_by(database.Highlight.start_offset)
            .options(joinedload(database.Highlight.tags))
        ).all()

        highlights = [
            (hl.start_offset, hl.end_offset, [t.path for t in hl.tags])
            for hl in highlights
        ]

        html = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: extract.highlight(
                doc.contents, highlights,
                show_tags=True,
            ),
        )
        html = self.render_string(
            'export_document.html',
            name=doc.name,
            contents=Markup(html),
        )
        # Drop non-ASCII characters from the name
        name = doc.name.encode('ascii', 'ignore').decode('ascii') or None
        return name, html


class ExportCodebookXml(BaseHandler):
    PROM_EXPORT.labels('codebook', 'qdc').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'qdc').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type', 'text/xml; charset=utf-8')
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.qdc"')

        # http://schema.qdasoftware.org/versions/Codebook/v1.0/Codebook.xsd
        output = XMLGenerator(WriteAdapter(self.write), encoding='utf-8',
                              short_empty_elements=True)
        output.startDocument()
        output.startPrefixMapping(None, 'urn:QDA-XML:codebook:1.0')
        refi_qda.write_codebook(tags, output)
        output.endPrefixMapping(None)
        output.endDocument()
        return self.finish()


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
        writer = csv.writer(WriteAdapter(self.write))
        writer.writerow(['tag', 'description'])
        for tag in tags:
            writer.writerow([tag.path, tag.description])
        return self.finish()


class ExportCodebookXlsx(BaseHandler):
    PROM_EXPORT.labels('codebook', 'xls').inc(0)

    @authenticated
    def get(self, project_id):
        PROM_EXPORT.labels('codebook', 'xls').inc()
        project, _ = self.get_project(project_id)
        tags = list(project.tags)
        self.set_header('Content-Type',
                        ('application/vnd.openxmlformats-officedocument.'
                         'spreadsheetml.sheet'))
        self.set_header('Content-Disposition',
                        'attachment; filename="codebook.xlsx"')
        tmp = tempfile.mkdtemp(prefix='taguette_xlsx_')
        try:
            filename = os.path.join(tmp, 'codebook.xlsx')
            workbook = xlsxwriter.Workbook(filename)
            sheet = workbook.add_worksheet('codebook')

            header = workbook.add_format({'bold': True})

            sheet.write(0, 0, 'tag', header)
            sheet.write(0, 1, 'description', header)
            sheet.set_column(0, 0, 30.0)
            sheet.set_column(1, 1, 80.0)
            for row, tag in enumerate(tags, start=1):
                sheet.write(row, 0, tag.path)
                sheet.write(row, 1, tag.description)
            workbook.close()
            with open(filename, 'rb') as fp:
                chunk = fp.read(4096)
                self.write(chunk)
                while len(chunk) == 4096:
                    chunk = fp.read(4096)
                    if chunk:
                        self.write(chunk)
            return self.finish()
        finally:
            shutil.rmtree(tmp)


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
