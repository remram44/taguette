import asyncio
import logging
from prometheus_async.aio import track_inprogress as prom_async_inprogress
import prometheus_client
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
from tornado.concurrent import Future
import tornado.log
from tornado.web import authenticated, HTTPError

from .. import convert
from .. import database
from .. import extract
from .. import validate
from .base import BaseHandler


logger = logging.getLogger(__name__)


PROM_POLLING_CLIENTS = prometheus_client.Gauge(
    'polling_clients',
    "Number of current polling clients",
)
PROM_API = prometheus_client.Counter(
    'api_total',
    "API requests",
    ['name'],
)


class ProjectMeta(BaseHandler):
    PROM_API.labels('project_meta').inc(0)

    @authenticated
    def post(self, project_id):
        PROM_API.labels('project_meta').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_edit_project_meta():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            obj = self.get_json()
            validate.project_name(obj['name'])
            project.name = obj['name']
            validate.project_description(obj['description'])
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
        except validate.InvalidFormat as e:
            logging.info("Error validating ProjectMeta: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class DocumentAdd(BaseHandler):
    PROM_API.labels('document_add').inc(0)

    @authenticated
    async def post(self, project_id):
        PROM_API.labels('document_add').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_add_document():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            name = self.get_body_argument('name')
            validate.document_name(name)
            description = self.get_body_argument('description')
            validate.document_description(description)
            file = self.request.files['file'][0]
            content_type = file.content_type
            filename = validate.filename(file.filename)

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
        except validate.InvalidFormat as e:
            logging.info("Error validating DocumentAdd: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class DocumentUpdate(BaseHandler):
    PROM_API.labels('document_update').inc(0)
    PROM_API.labels('document_delete').inc(0)

    @authenticated
    def post(self, project_id, document_id):
        PROM_API.labels('document_update').inc()
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_edit_document():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            obj = self.get_json()
            if obj:
                if 'name' in obj:
                    validate.document_name(obj['name'])
                    document.name = obj['name']
                if 'description' in obj:
                    validate.document_name(obj['description'])
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
        except validate.InvalidFormat as e:
            logging.info("Error validating DocumentUpdate: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})

    @authenticated
    def delete(self, project_id, document_id):
        PROM_API.labels('document_delete').inc()
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_delete_document():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
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
    PROM_API.labels('document_contents').inc(0)

    @authenticated
    def get(self, project_id, document_id):
        PROM_API.labels('document_contents').inc()
        document, _ = self.get_document(project_id, document_id, True)
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
    PROM_API.labels('tag_add').inc(0)

    @authenticated
    def post(self, project_id):
        PROM_API.labels('tag_add').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_add_tag():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            obj = self.get_json()
            validate.tag_path(obj['path'])
            validate.tag_description(obj['description'])
            tag = database.Tag(project=project,
                               path=obj['path'],
                               description=obj['description'])
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
        except validate.InvalidFormat as e:
            logging.info("Error validating TagAdd: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class TagUpdate(BaseHandler):
    PROM_API.labels('tag_update').inc(0)
    PROM_API.labels('tag_delete').inc(0)

    @authenticated
    def post(self, project_id, tag_id):
        PROM_API.labels('tag_update').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_update_tag():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            obj = self.get_json()
            tag = self.db.query(database.Tag).get(int(tag_id))
            if tag.project_id != project.id:
                raise HTTPError(404)
            if obj:
                if 'path' in obj:
                    validate.tag_path(obj['path'])
                    tag.path = obj['path']
                if 'description' in obj:
                    validate.tag_description(obj['description'])
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
        except validate.InvalidFormat as e:
            logging.info("Error validating TagUpdate: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})

    @authenticated
    def delete(self, project_id, tag_id):
        PROM_API.labels('tag_delete').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_tag():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
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
    PROM_API.labels('highlight_add').inc(0)

    @authenticated
    def post(self, project_id, document_id):
        PROM_API.labels('highlight_add').inc()
        document, privileges = self.get_document(project_id, document_id, True)
        if not privileges.can_add_highlight():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        obj = self.get_json()
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
    PROM_API.labels('highlight_update').inc(0)
    PROM_API.labels('highlight_delete').inc(0)

    @authenticated
    def post(self, project_id, document_id, highlight_id):
        PROM_API.labels('highlight_update').inc()
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_add_highlight():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        obj = self.get_json()
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
        PROM_API.labels('highlight_delete').inc()
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_delete_highlight():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
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
    PROM_API.labels('highlights').inc(0)

    @authenticated
    def get(self, project_id, path):
        PROM_API.labels('highlights').inc()
        project, _ = self.get_project(project_id)

        if path:
            tag = aliased(database.Tag)
            hltag = aliased(database.HighlightTag)
            highlights = (
                self.db.query(database.Highlight)
                .join(hltag, hltag.highlight_id == database.Highlight.id)
                .join(tag, hltag.tag_id == tag.id)
                .filter(tag.path.startswith(path))
                .filter(tag.project == project)
                .order_by(database.Highlight.document_id,
                          database.Highlight.start_offset)
            ).all()
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


class MembersUpdate(BaseHandler):
    PROM_API.labels('members_update').inc(0)

    @authenticated
    def patch(self, project_id):
        PROM_API.labels('members_update').inc()
        project, privileges = self.get_project(project_id)
        if not privileges.can_edit_members():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})

        # Get all members
        members = (
            self.db.query(database.ProjectMember)
            .filter(database.ProjectMember.project_id == project.id)
        ).all()
        members = {member.user_login: member for member in members}

        # Go over the JSON patch and update
        obj = self.get_json()
        commands = []
        for login, user in obj.items():
            if login == self.current_user:
                logger.warning("User tried to change own privileges")
                continue
            if not user and login in members:
                self.db.delete(members[login])
                cmd = database.Command.member_remove(
                    self.current_user, project.id,
                    login,
                )
                self.db.add(cmd)
                commands.append(cmd)
            else:
                try:
                    privileges = database.Privileges[user['privileges']]
                except KeyError:
                    self.set_status(400)
                    return self.send_json({'error': "Invalid privileges %r" %
                                                    user.get('privileges')})
                if login in members:
                    members[login].privileges = privileges
                else:
                    self.db.add(
                        database.ProjectMember(project=project,
                                               user_login=login,
                                               privileges=privileges)
                    )
                cmd = database.Command.member_add(
                    self.current_user, project.id,
                    login, privileges,
                )
                self.db.add(cmd)
                commands.append(cmd)

        self.db.commit()
        for cmd in commands:
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)

        self.set_status(204)
        self.finish()


class ProjectEvents(BaseHandler):
    PROM_API.labels('events').inc(0)

    response_cancelled = False

    @authenticated
    @prom_async_inprogress(PROM_POLLING_CLIENTS)
    async def get(self, project_id):
        PROM_API.labels('events').inc()
        from_id = int(self.get_query_argument('from'))
        project, _ = self.get_project(project_id)
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
        elif type_ == 'member_add':
            result = {
                'member_add': [{'member': payload['member'],
                                'privileges': payload['privileges']}]
            }
        elif type_ == 'member_remove':
            result = {
                'member_remove': [payload['member']]
            }
        else:
            raise ValueError("Unknown command type %r" % type_)

        result['id'] = cmd.id
        self.send_json(result)

    def on_connection_close(self):
        self.response_cancelled = True
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)

    def _log(self):
        if not self.response_cancelled:
            self.application.log_request(self)
        else:
            tornado.log.access_log.info(
                "aborted %s %s (%s) %.2fms",
                self.request.method,
                self.request.uri,
                self.request.remote_ip,
                1000.0 * self.request.request_time(),
            )
