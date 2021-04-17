import asyncio
import contextlib
import csv
import jinja2
import pkg_resources
import sqlalchemy
from markupsafe import Markup
from sqlalchemy.orm import joinedload
import uuid
import xlsxwriter
from xml.sax.saxutils import XMLGenerator
from xml.sax.xmlreader import AttributesNSImpl

from . import __version__ as version
from . import convert
from . import database
from . import extract


template_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        [pkg_resources.resource_filename('taguette', 'templates')]
    ),
    autoescape=jinja2.select_autoescape(['html']),
    extensions=['jinja2.ext.i18n'],
)


def _render_string(template_name, locale, **kwargs):
    translator = _Translator(locale)

    template = template_env.get_template(template_name)
    return template.render(
        version=version,
        gettext=translator.gettext,
        ngettext=translator.ngettext,
        **kwargs,
    )


class _Translator(object):
    def __init__(self, locale):
        self.locale = locale

    def gettext(self, message, **kwargs):
        trans = self.locale.translate(message)
        if kwargs:
            trans = trans % kwargs
        return trans

    def ngettext(self, singular, plural, n, **kwargs):
        trans = self.locale.translate(singular, plural, n)
        if kwargs:
            trans = trans % kwargs
        return trans


def _get_highlights_for_export(db, project_id, path):
    if path:
        t_highlight = database.Highlight.__table__
        t_highlight_tag = database.HighlightTag.__table__
        t_tag = database.Tag.__table__
        t_document = database.Document.__table__
        # Join with tags a second time to find highlights that match the
        # given path, while returning all tags for those highlights
        t_highlight_tag_m = database.HighlightTag.__table__.alias()
        t_tag_m = database.Tag.__table__.alias()
        query = (
            sqlalchemy.select([
                t_highlight.c.id,
                t_highlight.c.snippet,
                t_document.c.name,
                t_tag.c.path,
            ])
            .select_from(
                t_highlight
                .join(
                    t_highlight_tag,
                    t_highlight.c.id == t_highlight_tag.c.highlight_id,
                )
                .join(
                    t_tag,
                    t_tag.c.id == t_highlight_tag.c.tag_id,
                )
                .join(
                    t_highlight_tag_m,
                    t_highlight.c.id == t_highlight_tag_m.c.highlight_id,
                )
                .join(
                    t_tag_m,
                    t_tag_m.c.id == t_highlight_tag_m.c.tag_id,
                )
                .join(
                    t_document,
                    t_document.c.id == t_highlight.c.document_id,
                )
            )
            .where(t_tag_m.c.path.startswith(path))
            .where(t_document.c.project_id == project_id)
            .order_by(
                t_highlight.c.document_id,
                t_highlight.c.start_offset,
                t_highlight.c.id,
            )
        )
    else:
        # Special case to select all highlights: we also need to select
        # highlights that have no tag at all, so the startswith() condition
        # would not work
        t_highlight = database.Highlight.__table__
        t_highlight_tag = database.HighlightTag.__table__
        t_tag = database.Tag.__table__
        t_document = database.Document.__table__
        query = (
            sqlalchemy.select([
                t_highlight.c.id,
                t_highlight.c.snippet,
                t_document.c.name,
                t_tag.c.path,
            ])
            .select_from(
                t_highlight
                .join(
                    t_highlight_tag,
                    t_highlight.c.id == t_highlight_tag.c.highlight_id,
                )
                .join(
                    t_tag,
                    t_tag.c.id == t_highlight_tag.c.tag_id,
                )
                .join(
                    t_document,
                    t_document.c.id == t_highlight.c.document_id,
                )
            )
            .where(t_document.c.project_id == project_id)
            .order_by(
                t_highlight.c.document_id,
                t_highlight.c.start_offset,
                t_highlight.c.id,
            )
        )

    highlights = []
    for row in db.execute(query).fetchall():
        highlight_id, snippet, document, tag_path = row
        if highlights and highlights[-1][0] == highlight_id:
            highlights[-1][3].append(tag_path)
        else:
            highlights.append((
                highlight_id,
                snippet,
                document,
                [] if tag_path is None else [tag_path],
            ))

    return highlights


def get_filename_for_highlights_export(path):
    """Get a suitable filename for exported highlights.
    """
    if path:
        return None
    else:
        return 'all_tags'


def highlights_csv(db, project_id, path, file):
    """Export highlights to a CSV file.
    """
    highlights = _get_highlights_for_export(db, project_id, path)
    writer = csv.writer(file)
    writer.writerow(['id', 'document', 'tag', 'content'])
    for id, snippet, document, tags in highlights:
        if not tags:
            tags = ['']
        for tag_path in tags:
            writer.writerow([
                id, document, tag_path,
                convert.html_to_plaintext(snippet),
            ])


def highlights_xslx(db, project_id, path, filename):
    """Export highlights to an Excel file.
    """
    highlights = _get_highlights_for_export(db, project_id, path)

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
    for id, snippet, document, tags in highlights:
        if not tags:
            tags = ['']
        for tag_path in tags:
            sheet.write(row, 0, str(id))
            sheet.write(row, 1, document)
            sheet.write(row, 2, tag_path)
            sheet.write(row, 3, convert.html_to_plaintext(snippet))
            row += 1
    workbook.close()


def highlights_doc(db, project_id, path, ext, *, config, locale):
    """Export highlights to a text document.
    """
    highlights = _get_highlights_for_export(db, project_id, path)

    html = _render_string(
        'export_highlights.html',
        locale,
        path=path,
        highlights=highlights,
    )

    mimetype, contents = convert.html_to(html, ext, config)
    return mimetype, contents


async def highlighted_document(db, document, ext, *, config, locale):
    """Export a document annotated with highlights.

    Each highlight is followed by its tags in brackets.
    """
    highlights = (
        db.query(database.Highlight)
        .filter(database.Highlight.document_id == document.id)
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
            document.contents, highlights,
            show_tags=True,
        ),
    )

    html = _render_string(
        'export_document.html',
        locale,
        name=document.name,
        contents=Markup(html),
    )

    mimetype, contents = convert.html_to(
        html, ext,
        config,
    )
    contents = await contents
    return mimetype, contents


TAGUETTE_NAMESPACE = uuid.UUID('51B2B2B7-27EB-4ECB-9D56-E75B0A0496C2')


def codebook_xml(tags, file):
    """Export a codebook in REFI-QDA format for the given tags.
    """
    with contextlib.ExitStack() as stack:
        if not hasattr(file, 'write'):
            file = stack.enter_context(open(file, 'wb'))

        # http://schema.qdasoftware.org/versions/Codebook/v1.0/Codebook.xsd
        output = XMLGenerator(
            file,
            encoding='utf-8',
            short_empty_elements=True,
        )
        output.startDocument()
        output.startPrefixMapping(None, 'urn:QDA-XML:codebook:1.0')
        output.startElementNS(
            (None, 'CodeBook'), 'CodeBook',
            AttributesNSImpl({(None, 'origin'): 'Taguette %s' % version},
                             {(None, 'origin'): 'origin'}),
        )
        output.startElementNS(
            (None, 'Codes'), 'Codes',
            AttributesNSImpl({}, {}),
        )
        for tag in tags:
            guid = uuid.uuid5(TAGUETTE_NAMESPACE, tag.path)
            guid = str(guid).upper()
            output.startElementNS(
                (None, 'Code'), 'Code',
                AttributesNSImpl({(None, 'guid'): guid,
                                  (None, 'name'): tag.path,
                                  (None, 'isCodable'): 'true'},
                                 {(None, 'guid'): 'guid',
                                  (None, 'name'): 'name',
                                  (None, 'isCodable'): 'isCodable'}),
            )
            output.endElementNS((None, 'Code'), 'Code')
        output.endElementNS((None, 'Codes'), 'Codes')
        output.startElementNS(
            (None, 'Sets'), 'Sets',
            AttributesNSImpl({}, {}),
        )
        output.endElementNS((None, 'Sets'), 'Sets')
        output.endElementNS((None, 'CodeBook'), 'CodeBook')
        output.endPrefixMapping(None)
        output.endDocument()


def codebook_csv(tags, file):
    """Export a codebook in CSV format for the given tags.
    """
    with contextlib.ExitStack() as stack:
        if not hasattr(file, 'write'):
            file = stack.enter_context(open(file, 'w'))

        writer = csv.writer(file)
        writer.writerow(['tag', 'description', 'number of highlights'])
        for tag in tags:
            writer.writerow([tag.path, tag.description, tag.highlights_count])


def codebook_xlsx(tags, filename):
    """Export a codebook in Excel format for the given tags.
    """
    workbook = xlsxwriter.Workbook(filename)
    sheet = workbook.add_worksheet('codebook')

    header = workbook.add_format({'bold': True})

    sheet.write(0, 0, 'tag', header)
    sheet.write(0, 1, 'description', header)
    sheet.write(0, 2, 'number of highlights', header)
    sheet.set_column(0, 0, 30.0)
    sheet.set_column(1, 1, 80.0)
    for row, tag in enumerate(tags, start=1):
        sheet.write(row, 0, tag.path)
        sheet.write(row, 1, tag.description)
        sheet.write(row, 2, tag.highlights_count)
    workbook.close()


async def codebook_document(tags, ext, *, config, locale):
    """Export a codebook as a text document for the given tags.
    """
    html = _render_string(
        'export_codebook.html',
        locale,
        tags=tags,
    )

    mimetype, contents = convert.html_to(
        html, ext,
        config,
    )
    contents = await contents
    return mimetype, contents
