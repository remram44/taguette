import asyncio
import functools
import json
import logging
import math
import prometheus_client
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, defer, joinedload
import tempfile
from tornado.concurrent import Future
import tornado.log
from tornado.web import MissingArgumentError, HTTPError

from .. import convert
from .. import database
from .. import extract
from .. import validate
from .base import BaseHandler, PromMeasureRequest


logger = logging.getLogger(__name__)


PROM_POLLING_CLIENTS = prometheus_client.Gauge(
    'polling_clients',
    "Number of current polling clients",
)

PROM_REQUESTS = PromMeasureRequest(
    count=prometheus_client.Counter(
        'api_total',
        "API requests",
        ['name'],
    ),
    time=prometheus_client.Histogram(
        'api_seconds',
        "API request time",
        ['name'],
    ),
)


def api_auth(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            return self.send_error_json(403, "Not logged in")
        return method(self, *args, **kwargs)

    return wrapper


class CheckUser(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('check_user')
    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        login = self.get_json()['login']
        try:
            login = validate.user_login(login)
        except validate.InvalidFormat:
            pass
        else:
            user = self.db.query(database.User).get(login)
            if user is not None:
                return self.send_json({'exists': True})
        return self.send_json({'exists': False})


class ProjectMeta(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('project_meta')
    def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_edit_project_meta():
            return self.send_error_json(403, "Unauthorized")
        try:
            obj = self.get_json()
            validate.project_name(obj['name'])
            project.name = obj['name']
            validate.description(obj['description'])
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
            logger.info("Error validating ProjectMeta: %r", e)
            return self.send_error_json(e.status_code, self.gettext(e.message),
                                        e.reason)


class DocumentAdd(BaseHandler):
    @api_auth
    @PROM_REQUESTS.async_('document_add')
    async def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_add_document():
            return await self.send_error_json(403, "Unauthorized")
        try:
            name = self.get_body_argument('name')
            validate.document_name(name)
            description = self.get_body_argument('description')
            validate.description(description)
            try:
                file = self.request.files['file'][0]
            except (KeyError, IndexError):
                raise MissingArgumentError('file')
            content_type = file.content_type
            filename = validate.filename(file.filename)

            try:
                body = await convert.to_html_chunks(
                    file.body, content_type, filename,
                    self.application.config,
                )
            except convert.ConversionError as err:
                return await self.send_error_json(400, str(err))
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
                return await self.send_json({'created': doc.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating DocumentAdd: %r", e)
            return await self.send_error_json(
                e.status_code, self.gettext(e.message),
                e.reason,
            )


class DocumentUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('document_update')
    def post(self, project_id, document_id):
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_edit_document():
            return self.send_error_json(403, "Unauthorized")
        try:
            obj = self.get_json()
            if obj:
                if 'name' in obj:
                    validate.document_name(obj['name'])
                    document.name = obj['name']
                if 'description' in obj:
                    validate.description(obj['description'])
                    document.description = obj['description']
                cmd = database.Command.document_add(
                    self.current_user,
                    document,
                )
                self.db.add(cmd)
                self.db.commit()
                self.db.refresh(cmd)
                self.application.notify_project(document.project_id, cmd)

            return self.send_json({'id': document.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating DocumentUpdate: %r", e)
            return self.send_error_json(e.status_code, self.gettext(e.message),
                                        e.reason)

    @api_auth
    @PROM_REQUESTS.sync('document_delete')
    def delete(self, project_id, document_id):
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_delete_document():
            return self.send_error_json(403, "Unauthorized")
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
        return self.finish()


class DocumentContents(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('document_contents')
    def get(self, project_id, document_id):
        document, _ = self.get_document(project_id, document_id, True)

        highlights = (
            self.db.query(database.Highlight)
            .options(defer('snippet'))
            .filter(database.Highlight.document_id == document.id)
            .order_by(database.Highlight.start_offset)
            .options(joinedload(database.Highlight.tags))
            .options(defer('tags.highlights_count'))
        ).all()

        return self.send_json({
            'contents': [
                {'offset': 0, 'contents': document.contents},
            ],
            'highlights': [
                {'id': hl.id,
                 'start_offset': hl.start_offset,
                 'end_offset': hl.end_offset,
                 'tags': [t.id for t in hl.tags]}
                for hl in highlights
            ],
        })


class TagAdd(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('tag_add')
    def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_add_tag():
            return self.send_error_json(403, "Unauthorized")
        try:
            obj = self.get_json()
            validate.tag_path(obj['path'])
            validate.description(obj['description'])
            tag = database.Tag(project=project,
                               path=obj['path'],
                               description=obj['description'])
            try:
                self.db.add(tag)
                self.db.flush()  # Need to flush to get tag.id
            except IntegrityError:
                self.db.rollback()
                return self.send_error_json(409, "Conflict")
            cmd = database.Command.tag_add(
                self.current_user,
                tag,
            )
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)

            return self.send_json({'id': tag.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating TagAdd: %r", e)
            return self.send_error_json(e.status_code, self.gettext(e.message),
                                        e.reason)


class TagUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('tag_update')
    def post(self, project_id, tag_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_update_tag():
            return self.send_error_json(403, "Unauthorized")
        try:
            obj = self.get_json()
            tag = self.db.query(database.Tag).get(int(tag_id))
            if tag is None or tag.project_id != project.id:
                return self.send_error_json(404, "No such tag")
            if obj:
                if 'path' in obj:
                    validate.tag_path(obj['path'])
                    tag.path = obj['path']
                if 'description' in obj:
                    validate.description(obj['description'])
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
                    return self.send_error_json(409, "Conflict")
                self.db.refresh(cmd)
                self.application.notify_project(project.id, cmd)

            return self.send_json({'id': tag.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating TagUpdate: %r", e)
            return self.send_error_json(e.status_code, self.gettext(e.message),
                                        e.reason)

    @api_auth
    @PROM_REQUESTS.sync('tag_delete')
    def delete(self, project_id, tag_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_tag():
            return self.send_error_json(403, "Unauthorized")
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag is None or tag.project_id != project.id:
            return self.send_error_json(404, "No such tag")
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
        return self.finish()


class TagMerge(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('tag_merge')
    def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_merge_tags():
            return self.send_error_json(403, "Unauthorized")
        obj = self.get_json()
        tag_src = self.db.query(database.Tag).get(obj['src'])
        tag_dest = self.db.query(database.Tag).get(obj['dest'])
        if (
            tag_src is None
            or tag_src.project_id != project.id
            or tag_dest is None
            or tag_dest.project_id != project.id
        ):
            return self.send_error_json(404, "No such tag")

        # Remove tag from tag_src if it's already in tag_dest
        highlights_in_dest = (
            self.db.query(database.HighlightTag.highlight_id)
            .filter(database.HighlightTag.tag_id == tag_dest.id)
        )
        (
            self.db.query(database.HighlightTag)
                .filter(database.HighlightTag.tag_id == tag_src.id)
                .filter(database.HighlightTag.highlight_id.in_(
                    highlights_in_dest
                ))
        ).delete(synchronize_session=False)
        # Update tags that are in tag_src to be in tag_dest
        self.db.execute(
            database.HighlightTag.__table__.update()
            .where(database.HighlightTag.tag_id == tag_src.id)
            .values(tag_id=tag_dest.id)
        )
        # Delete tag_src
        self.db.delete(tag_src)

        cmd = database.Command.tag_merge(
            self.current_user,
            project.id,
            tag_src.id,
            tag_dest.id,
        )
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(project.id, cmd)

        return self.send_json({'id': tag_dest.id})


class HighlightAdd(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('highlight_add')
    def post(self, project_id, document_id):
        document, privileges = self.get_document(project_id, document_id, True)
        if not privileges.can_add_highlight():
            return self.send_error_json(403, "Unauthorized")
        obj = self.get_json()
        start, end = obj['start_offset'], obj['end_offset']
        new_tags = set(obj.get('tags', []))

        # Check the tags exist and are in this project
        tags = (
            self.db.query(database.Tag)
            .filter(database.Tag.id.in_(new_tags))
            .filter(database.Tag.project_id == document.project_id)
            .all()
        )
        if set(tag.id for tag in tags) != new_tags:
            return self.send_error_json(400, "Tag not in project")

        snippet = extract.extract(document.contents, start, end)
        hl = database.Highlight(document=document,
                                start_offset=start,
                                end_offset=end,
                                snippet=snippet)
        self.db.add(hl)
        self.db.flush()  # Need to flush to get hl.id

        # Insert tags in database
        self.db.bulk_insert_mappings(database.HighlightTag, [
            dict(
                highlight_id=hl.id,
                tag_id=tag,
            )
            for tag in sorted(new_tags)
        ])
        cmd = database.Command.highlight_add(
            self.current_user,
            document,
            hl,
            sorted(new_tags),
        )
        cmd.tag_count_changes = {tag: 1 for tag in obj.get('tags')}
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        return self.send_json({'id': hl.id})


class HighlightUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('highlight_update')
    def post(self, project_id, document_id, highlight_id):
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_add_highlight():
            return self.send_error_json(403, "Unauthorized")
        obj = self.get_json()
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl is None or hl.document_id != document.id:
            return self.send_error_json(404, "No such highlight")
        if obj:
            if 'start_offset' in obj:
                hl.start_offset = obj['start_offset']
            if 'end_offset' in obj:
                hl.end_offset = obj['end_offset']
            if 'tags' in obj:
                # Obtain old tags from database
                old_tags = (
                    self.db.query(database.HighlightTag)
                    .filter(database.HighlightTag.highlight == hl)
                    .all()
                )
                old_tags = set(hl_tag.tag_id for hl_tag in old_tags)
                new_tags = set(obj['tags'])

                # Check the tags exist and are in this project
                tags = (
                    self.db.query(database.Tag)
                        .filter(database.Tag.id.in_(new_tags))
                        .filter(database.Tag.project_id == document.project_id)
                        .all()
                )
                if set(tag.id for tag in tags) != new_tags:
                    return self.send_error_json(400, "Tag not in project")

                # Update tags in database
                (
                    self.db.query(database.HighlightTag)
                    .filter(database.HighlightTag.highlight == hl)
                ).delete()
                self.db.bulk_insert_mappings(database.HighlightTag, [
                    dict(
                        highlight_id=hl.id,
                        tag_id=tag,
                    )
                    for tag in sorted(new_tags)
                ])

                # Compute the change in tag counts
                tag_count_changes = {}
                for tag in old_tags - new_tags:
                    tag_count_changes[tag] = -1
                for tag in new_tags - old_tags:
                    tag_count_changes[tag] = 1
            else:
                new_tags = None
                tag_count_changes = None

            cmd = database.Command.highlight_add(
                self.current_user,
                document,
                hl,
                sorted(new_tags),
            )
            cmd.tag_count_changes = tag_count_changes
            self.db.add(cmd)
            self.db.commit()
            self.db.refresh(cmd)
            self.application.notify_project(document.project_id, cmd)

        return self.send_json({'id': hl.id})

    @api_auth
    @PROM_REQUESTS.sync('highlight_delete')
    def delete(self, project_id, document_id, highlight_id):
        document, privileges = self.get_document(project_id, document_id)
        if not privileges.can_delete_highlight():
            return self.send_error_json(403, "Unauthorized")
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl is None or hl.document_id != document.id:
            return self.send_error_json(404, "No such highlight")
        old_tags = list(
            self.db.query(database.HighlightTag)
            .filter(database.HighlightTag.highlight == hl)
            .all()
        )
        old_tags = [hl_tag.tag_id for hl_tag in old_tags]
        self.db.delete(hl)
        cmd = database.Command.highlight_delete(
            self.current_user,
            document,
            hl.id,
        )
        cmd.tag_count_changes = {tag: -1 for tag in old_tags}
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)
        self.application.notify_project(document.project_id, cmd)

        self.set_status(204)
        return self.finish()


class Highlights(BaseHandler):
    PAGE_SIZE = 50

    @api_auth
    @PROM_REQUESTS.sync('highlights')
    def get(self, project_id, path):
        project, _ = self.get_project(project_id)
        page = self.get_query_argument('page', '1')
        try:
            page = int(page, 10) - 1
        except (ValueError, OverflowError):
            page = -1
        if page < 0:
            self.send_error_json(404, "Bad page number")

        if path:
            tag = aliased(database.Tag)
            hltag = aliased(database.HighlightTag)
            query = (
                self.db.query(database.Highlight)
                .options(joinedload(database.Highlight.tags))
                .join(hltag, hltag.highlight_id == database.Highlight.id)
                .join(tag, hltag.tag_id == tag.id)
                .filter(tag.path.startswith(path))
                .filter(tag.project == project)
                .order_by(database.Highlight.document_id,
                          database.Highlight.start_offset)
            )
        else:
            # Special case to select all highlights: we also need to select
            # highlights that have no tag at all
            document = aliased(database.Document)
            query = (
                self.db.query(database.Highlight)
                .options(joinedload(database.Highlight.tags))
                .join(document, document.id == database.Highlight.document_id)
                .filter(document.project == project)
                .order_by(database.Highlight.document_id,
                          database.Highlight.start_offset)
            )

        total = query.count()
        highlights = (
            query
            .offset(page * self.PAGE_SIZE)
            .limit(self.PAGE_SIZE)
            .all()
        )

        return self.send_json({
            'highlights': [
                {
                    'id': hl.id,
                    'document_id': hl.document_id,
                    'content': hl.snippet,
                    'tags': [t.id for t in hl.tags],
                }
                for hl in highlights
            ],
            'pages': math.ceil(total / self.PAGE_SIZE),
        })


class MembersUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('members_update')
    def patch(self, project_id):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        obj = self.get_json()
        project, privileges = self.get_project(project_id)

        if (obj.keys() == {self.current_user} and
                not obj[self.current_user]):
            # Special case: you are always allowed to remove yourself
            pass
        elif not privileges.can_edit_members():
            return self.send_error_json(403, "Unauthorized")

        # Get all members
        members = (
            self.db.query(database.ProjectMember)
            .filter(database.ProjectMember.project_id == project.id)
        ).all()
        members = {member.user_login: member for member in members}

        # Go over the JSON patch and update
        commands = []
        for login, user_info in obj.items():
            login = validate.user_login(login)
            if not user_info:
                if login in members:
                    logger.info("Removing member %r from project %d (%s)",
                                login, project.id, members[login].privileges)
                    self.db.delete(members.pop(login))
                    cmd = database.Command.member_remove(
                        self.current_user, project.id,
                        login,
                    )
                    self.db.add(cmd)
                    commands.append(cmd)
            else:
                try:
                    privileges = database.Privileges[user_info['privileges']]
                except KeyError:
                    return self.send_error_json(
                        400,
                        "Invalid privileges %r" % user_info.get('privileges'),
                    )
                if login in members:
                    logger.info("Changing member %r in project %d: %s -> %s",
                                login, project.id, members[login].privileges,
                                privileges)
                    members[login].privileges = privileges
                else:
                    logger.info("Adding member %r to project %d (%s)",
                                login, project.id, privileges)
                    member = database.ProjectMember(project=project,
                                                    user_login=login,
                                                    privileges=privileges)
                    members[login] = member
                    self.db.add(member)
                cmd = database.Command.member_add(
                    self.current_user, project.id,
                    login, privileges,
                )
                self.db.add(cmd)
                commands.append(cmd)

        # Check that there are still admins
        for member in members.values():
            if member.privileges == database.Privileges.ADMIN:
                break
        else:
            self.db.rollback()
            return self.send_error_json(400, "There must be one admin")

        self.db.commit()
        for cmd in commands:
            self.db.refresh(cmd)
            self.application.notify_project(project.id, cmd)

        self.set_status(204)
        return self.finish()


class ImportProject(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('project_import')
    async def post(self):
        try:
            file = self.request.files['file'][0]
        except (KeyError, IndexError):
            raise MissingArgumentError('file')

        with tempfile.NamedTemporaryFile(
            'wb',
            prefix='taguette_import_',
            suffix='.sqlite3',
        ) as tmp:
            # Write the database to temporary file
            tmp.write(file.body)
            tmp.flush()

            project_id = self.get_body_argument('project_id', None)
            if project_id is None:
                return await self._list_projects(tmp.name)
            else:
                try:
                    project_id = int(project_id)
                except ValueError:
                    self.set_status(400)
                    return await self.send_json({
                        'error': "Invalid project ID",
                    })
                return await self._import_project(tmp.name, project_id)

    async def _list_projects(self, filename):
        # Connect to the database
        src_db = database.connect('sqlite:///%s' % filename, external=True)()

        # List projects
        projects = src_db.execute(database.Project.__table__.select())
        for i, row in enumerate(projects):
            if i == 0:
                self.set_header(
                    'Content-Type', 'application/json; charset=utf-8',
                )
                self.write('{"projects": [')
            else:
                self.write(',')
            self.write(json.dumps({
                'id': row['id'],
                'name': row['name'],
            }))
            if i == 100:
                await self.flush()
        return await self.finish(']}')

    async def _import_project(self, filename, project_id):
        # Connect to the database
        src_db = database.connect('sqlite:///%s' % filename, external=True)()

        # Copy data
        new_project_id = database.copy_project(
            src_db, self.db,
            project_id, self.current_user,
        )
        src_db.close()

        # Insert a command for the import
        self.db.add(
            database.Command.project_import(self.current_user, new_project_id)
        )

        self.db.commit()

        return await self.send_json({'project_id': new_project_id})


class ProjectEvents(BaseHandler):
    response_cancelled = False
    polling_clients = set()
    PROM_POLLING_CLIENTS.set_function(
        lambda: len(ProjectEvents.polling_clients)
    )

    @api_auth
    @PROM_REQUESTS.async_('events')
    async def get(self, project_id):
        ProjectEvents.polling_clients.add(self.request.remote_ip)
        tornado.log.access_log.info(
            "started %s %s (%s) (%s)",
            self.request.method,
            self.request.uri,
            self.request.remote_ip,
            self.current_user,
        )

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

            # Close DB connection to not overflow the connection pool
            self.close_db_connection()

            try:
                cmd = await self.wait_future
            except asyncio.CancelledError:
                return

        payload = dict(cmd.payload)
        type_ = payload.pop('type', None)
        if type_ == 'project_meta':
            result = {'project_meta': payload}
        elif type_ == 'document_add':
            payload['document_id'] = cmd.document_id
            result = {'document_add': [payload]}
        elif type_ == 'document_delete':
            result = {'document_delete': [cmd.document_id]}
        elif type_ == 'highlight_add':
            result = {'highlight_add': {cmd.document_id: [payload]}}
        elif type_ == 'highlight_delete':
            result = {
                'highlight_delete': {
                    cmd.document_id: [payload['highlight_id']],
                }
            }
        elif type_ == 'tag_add':
            result = {
                'tag_add': [payload],
            }
        elif type_ == 'tag_delete':
            result = {
                'tag_delete': [payload['tag_id']],
            }
        elif type_ == 'tag_merge':
            result = {
                'tag_merge': [payload],
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

        if cmd.tag_count_changes is not None:
            result['tag_count_changes'] = cmd.tag_count_changes

        result['id'] = cmd.id
        return await self.send_json(result)

    def on_connection_close(self):
        self.response_cancelled = True
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)

    def on_finish(self):
        super(ProjectEvents, self).on_finish()
        ProjectEvents.polling_clients.discard(self.request.remote_ip)

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
