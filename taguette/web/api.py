import asyncio
import os
import logging
import re
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
import sys
from tornado.concurrent import Future
from tornado.web import authenticated, HTTPError

from .. import convert
from .. import database
from .. import extract
from .base import BaseHandler


logger = logging.getLogger(__name__)


class ProjectMeta(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        project.name = obj['name']
        project.description = obj['description']
        logger.info("Updated project: %r %r",
                    project.name, project.description)
        cmd = database.Command.project_meta(
            self.current_user,
            project.id,
            obj['name'],
            obj['description'],
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)
        return self.send_json({})


_windows_device_files = ('CON', 'AUX', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1',
                         'LPT2', 'LPT3', 'PRN', 'NUL')
_not_ascii_re = re.compile(r'[^A-Za-z0-9_.-]')


def secure_filename(name):
    """Sanitize a filename.

    This takes a filename, for example provided by a browser with a file
    upload, and turn it into something that is safe for opening.

    Adapted from werkzeug's secure_filename(), copyright 2007 the Pallets team.
    https://palletsprojects.com/p/werkzeug/
    """
    if '/' in name:
        name = name[name.rindex('/') + 1:]
    if sys.platform == 'win32' and '\\' in name:
        # It seems that IE gets that wrong, at least when the file is from
        # a network share
        name = name[name.rindex('\\') + 1:]
    name = _not_ascii_re.sub('', name).strip('._')
    if not name:
        return '_'
    if os.name == 'nt' and name.split('.')[0].upper() in _windows_device_files:
        name = '_' + name
    return name


class DocumentAdd(BaseHandler):
    @authenticated
    async def post(self, project_id):
        project = self.get_project(project_id)

        name = self.get_body_argument('name')
        description = self.get_body_argument('description')
        file = self.request.files['file'][0]
        content_type = file.content_type
        filename = secure_filename(file.filename)

        try:
            body = await convert.to_html_chunks(file.body, content_type,
                                                filename)
        except convert.ConversionError as err:
            self.set_status(400)
            self.send_json({
                'error': str(err),
            })
        else:
            doc = database.Document(
                name=name,
                description=description,
                filename=filename,
                project=project,
                contents=body,
            )
            self.db.add(doc)
            self.db.flush()  # Need to flush to get doc.id
            cmd = database.Command.document_add(
                self.current_user,
                doc,
            )
            self.db.add(cmd)
            logger.info("Document added to project %r: %r %r (%d bytes)",
                        project.id, doc.id, doc.name, len(doc.contents))
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)
            self.send_json({'created': doc.id})


class DocumentUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, document_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id)
        if obj:
            if 'name' in obj:
                document.name = obj['name']
            if 'description' in obj:
                document.description = obj['description']
            cmd = database.Command.document_add(
                self.current_user,
                document,
            )
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': document.id})

    @authenticated
    def delete(self, project_id, document_id):
        document = self.get_document(project_id, document_id)
        self.db.delete(document)
        cmd = database.Command.document_delete(
            self.current_user,
            document,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.set_status(204)
        self.finish()


class DocumentContents(BaseHandler):
    @authenticated
    def get(self, project_id, document_id):
        document = self.get_document(project_id, document_id, True)
        self.send_json({
            'contents': [
                {'offset': 0, 'contents': document.contents},
            ],
            'highlights': [
                {'id': hl.id,
                 'start_offset': hl.start_offset,
                 'end_offset': hl.end_offset,
                 'tags': [t.id for t in hl.tags]}
                for hl in document.highlights
            ],
        })


class TagAdd(BaseHandler):
    @authenticated
    def post(self, project_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        tag = database.Tag(project=project,
                           path=obj['path'], description=obj['description'])
        try:
            self.db.add(tag)
            self.db.flush()  # Need to flush to get tag.id
        except IntegrityError:
            self.db.rollback()
            self.set_status(409)
            return self.finish()
        cmd = database.Command.tag_add(
            self.current_user,
            tag,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)

        self.send_json({'id': tag.id})


class TagUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, tag_id):
        obj = self.get_json()
        project = self.get_project(project_id)
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag.project_id != project.id:
            raise HTTPError(404)
        if obj:
            if 'path' in obj:
                tag.path = obj['path']
            if 'description' in obj:
                tag.description = obj['description']
            cmd = database.Command.tag_add(
                self.current_user,
                tag,
            )
            try:
                self.db.add(cmd)
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                self.set_status(409)
                return self.finish()
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)

        self.send_json({'id': tag.id})

    @authenticated
    def delete(self, project_id, tag_id):
        project = self.get_project(project_id)
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag.project_id != project.id:
            raise HTTPError(404)
        self.db.delete(tag)
        cmd = database.Command.tag_delete(
            self.current_user,
            project.id,
            tag.id,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)

        self.set_status(204)
        self.finish()


class HighlightAdd(BaseHandler):
    @authenticated
    def post(self, project_id, document_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id, True)
        start, end = obj['start_offset'], obj['end_offset']
        snippet = extract.extract(document.contents, start, end)
        hl = database.Highlight(document=document,
                                start_offset=start,
                                end_offset=end,
                                snippet=snippet)
        self.db.add(hl)
        self.db.flush()  # Need to flush to get hl.id
        self.db.bulk_insert_mappings(database.HighlightTag, [
            dict(
                highlight_id=hl.id,
                tag_id=tag,
            )
            for tag in obj.get('tags', [])
        ])
        cmd = database.Command.highlight_add(
            self.current_user,
            document,
            hl,
            obj.get('tags', []),
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': hl.id})


class HighlightUpdate(BaseHandler):
    @authenticated
    def post(self, project_id, document_id, highlight_id):
        obj = self.get_json()
        document = self.get_document(project_id, document_id)
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl.document_id != document.id:
            raise HTTPError(404)
        if obj:
            if 'start_offset' in obj:
                hl.start_offset = obj['start_offset']
            if 'end_offset' in obj:
                hl.end_offset = obj['end_offset']
            if 'tags' in obj:
                (
                    self.db.query(database.HighlightTag)
                    .filter(database.HighlightTag.highlight == hl)
                ).delete()
                self.db.bulk_insert_mappings(database.HighlightTag, [
                    dict(
                        highlight_id=hl.id,
                        tag_id=tag,
                    )
                    for tag in obj.get('tags', [])
                ])
            cmd = database.Command.highlight_add(
                self.current_user,
                document,
                hl,
                obj.get('tags', []),
            )
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(document.project_id, cmd)

        self.send_json({'id': hl.id})

    @authenticated
    def delete(self, project_id, document_id, highlight_id):
        document = self.get_document(project_id, document_id)
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl.document_id != document.id:
            raise HTTPError(404)
        self.db.delete(hl)
        cmd = database.Command.highlight_delete(
            self.current_user,
            document,
            hl.id,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.set_status(204)
        self.finish()


class Highlights(BaseHandler):
    @authenticated
    def get(self, project_id, path):
        project = self.get_project(project_id)

        tag = aliased(database.Tag)
        hltag = aliased(database.HighlightTag)
        highlights = (
            self.db.query(database.Highlight)
            .join(hltag, hltag.highlight_id == database.Highlight.id)
            .join(tag, hltag.tag_id == tag.id)
            .filter(tag.path.startswith(path))
            .filter(tag.project == project)
        ).all()

        self.send_json({
            'highlights': [
                {
                    'id': hl.id,
                    'document_id': hl.document_id,
                    'content': hl.snippet,
                    'tags': [t.id for t in hl.tags],
                }
                for hl in highlights
            ],
        })


class ProjectEvents(BaseHandler):
    @authenticated
    async def get(self, project_id):
        from_id = int(self.get_query_argument('from'))
        project = self.get_project(project_id)
        self.project_id = int(project_id)

        # Check for immediate update
        cmd = (
            self.db.query(database.Command)
            .filter(database.Command.id > from_id)
            .filter(database.Command.project_id == project.id)
            .limit(1)
        ).one_or_none()

        # Wait for an event
        if cmd is None:
            self.wait_future = Future()
            self.application.observe_project(project.id, self.wait_future)
            self.db.expire_all()
            try:
                cmd = await self.wait_future
            except asyncio.CancelledError:
                return

        payload = dict(cmd.payload)
        type_ = payload.pop('type', None)
        if type_ == 'project_meta':
            result = {'project_meta': payload}
        elif type_ == 'document_add':
            payload['id'] = cmd.document_id
            result = {'document_add': [payload]}
        elif type_ == 'document_delete':
            result = {'document_delete': [cmd.document_id]}
        elif type_ == 'highlight_add':
            result = {'highlight_add': {cmd.document_id: [payload]}}
        elif type_ == 'highlight_delete':
            result = {
                'highlight_delete': {cmd.document_id: [payload['id']]}
            }
        elif type_ == 'tag_add':
            result = {
                'tag_add': [payload],
            }
        elif type_ == 'tag_delete':
            result = {
                'tag_delete': [payload['id']],
            }
        else:
            raise ValueError("Unknown command type %r" % type_)

        result['id'] = cmd.id
        self.send_json(result)

    def on_connection_close(self):
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)
