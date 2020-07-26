import asyncio
import functools
import logging
import prometheus_client
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
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
            self.set_status(403)
            return self.send_json({'error': "Not logged in"})
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
            logger.info("Error validating ProjectMeta: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class DocumentAdd(BaseHandler):
    @api_auth
    @PROM_REQUESTS.async_('document_add')
    async def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_add_document():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            name = self.get_body_argument('name')
            validate.document_name(name)
            description = self.get_body_argument('description')
            validate.document_description(description)
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
                self.set_status(400)
                return self.send_json({
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
                return self.send_json({'created': doc.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating DocumentAdd: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class DocumentUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('document_update')
    def post(self, project_id, document_id):
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
                    validate.document_description(obj['description'])
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
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})

    @api_auth
    @PROM_REQUESTS.sync('document_delete')
    def delete(self, project_id, document_id):
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
        return self.finish()


class DocumentContents(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('document_contents')
    def get(self, project_id, document_id):
        document, _ = self.get_document(project_id, document_id, True)
        return self.send_json({
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
    @api_auth
    @PROM_REQUESTS.sync('tag_add')
    def post(self, project_id):
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

            return self.send_json({'id': tag.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating TagAdd: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})


class TagUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('tag_update')
    def post(self, project_id, tag_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_update_tag():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        try:
            obj = self.get_json()
            tag = self.db.query(database.Tag).get(int(tag_id))
            if tag is None or tag.project_id != project.id:
                self.set_status(404)
                return self.send_json({'error': "No such tag"})
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

            return self.send_json({'id': tag.id})
        except validate.InvalidFormat as e:
            logger.info("Error validating TagUpdate: %r", e)
            self.set_status(e.status_code, e.reason)
            return self.send_json({'error': e.message})

    @api_auth
    @PROM_REQUESTS.sync('tag_delete')
    def delete(self, project_id, tag_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_tag():
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        tag = self.db.query(database.Tag).get(int(tag_id))
        if tag is None or tag.project_id != project.id:
            self.set_status(404)
            return self.send_json({'error': "No such tag"})
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
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        obj = self.get_json()
        tag_src = self.db.query(database.Tag).get(obj['src'])
        tag_dest = self.db.query(database.Tag).get(obj['dest'])
        if (
            tag_src is None
            or tag_src.project_id != project.id
            or tag_dest is None
            or tag_dest.project_id != project.id
        ):
            self.set_status(404)
            return self.send_json({'error': "No such tag"})

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
        new_tags = sorted(set(obj.get('tags', [])))
        self.db.bulk_insert_mappings(database.HighlightTag, [
            dict(
                highlight_id=hl.id,
                tag_id=tag,
            )
            for tag in new_tags
        ])
        cmd = database.Command.highlight_add(
            self.current_user,
            document,
            hl,
            new_tags,
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
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        obj = self.get_json()
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl is None or hl.document_id != document.id:
            self.set_status(404)
            return self.send_json({'error': "No such highlight"})
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
                    for tag in new_tags
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
            self.set_status(403)
            return self.send_json({'error': "Unauthorized"})
        hl = self.db.query(database.Highlight).get(int(highlight_id))
        if hl is None or hl.document_id != document.id:
            self.set_status(404)
            return self.send_json({'error': "No such highlight"})
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
    @api_auth
    @PROM_REQUESTS.sync('highlights')
    def get(self, project_id, path):
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
        })


class MembersUpdate(BaseHandler):
    @api_auth
    @PROM_REQUESTS.sync('members_update')
    def patch(self, project_id):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
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
            login = validate.user_login(login)
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
        return self.finish()


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
            "started %s %s (%s)",
            self.request.method,
            self.request.uri,
            self.request.remote_ip,
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
        elif type_ == 'tag_merge':
            result = {
                'tag_merge': [
                    {'src': payload['src'], 'dest': payload['dest']},
                ],
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
        return self.send_json(result)

    def on_connection_close(self):
        self.response_cancelled = True
        self.wait_future.cancel()
        self.application.unobserve_project(self.project_id, self.wait_future)

    def on_finish(self):
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
