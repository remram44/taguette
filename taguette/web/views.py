import asyncio
from datetime import timedelta, datetime
from email.message import EmailMessage
import io
import itertools
import json
import logging
from markupsafe import Markup
import prometheus_client
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased
import time
import tornado.locale
from tornado.web import authenticated, HTTPError
from urllib.parse import urlunparse

from .. import database
from .. import import_codebook
from ..utils import _f
from .. import validate
from .base import BaseHandler, PromMeasureRequest


logger = logging.getLogger(__name__)


PROM_REQUESTS = PromMeasureRequest(
    count=prometheus_client.Counter(
        'pages_total',
        "Page requests",
        ['name'],
    ),
    time=prometheus_client.Histogram(
        'page_seconds',
        "Page request time",
        ['name'],
    ),
)


class Index(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    @PROM_REQUESTS.sync('index')
    def get(self):
        if self.current_user is not None:
            if self.get_query_argument('token', None):
                return self.redirect(self.reverse_url('index'))
            user = self.db.query(database.User).get(self.current_user)
            if user is None:
                logger.warning("User is logged in as non-existent user %r",
                               self.current_user)
                self.logout()
                # Fall through to welcome page
            else:
                return self.render('index.html',
                                   user=user, projects=user.projects,
                                   can_import_project=self.application.config[
                                       'SQLITE3_IMPORT_ENABLED'])
        elif not self.application.config['MULTIUSER']:
            token = self.get_query_argument('token', None)
            if token and token == self.application.single_user_token:
                self.login('admin')
                return self.redirect(self.reverse_url('index'))
            elif token:
                return self.redirect(self.reverse_url('index'))
            else:
                return self.render('token_needed.html')
        return self.render('welcome.html')

    head = get


class CookiesPrompt(BaseHandler):
    @PROM_REQUESTS.sync('cookies_prompt')
    def get(self):
        return self.render('cookies_prompt.html',
                           next=self.get_argument('next', ''))

    @PROM_REQUESTS.sync('cookies_prompt')
    def post(self):
        self.set_cookie('cookies_accepted', 'yes', dont_check=True)
        next_ = self.get_argument('next', '')
        if not next_:
            next_ = self.reverse_url('index')
        return self.redirect(next_)

    def check_xsrf_cookie(self):
        pass


class BrokenBasePath(BaseHandler):
    def get(self):
        self.set_header('Content-Type', 'text/plain')
        return self.finish((
            "Error: BASE_PATH is set to {0} so you shouldn't be reaching this "
            + "page.\n"
            + "\n"
            + "You might need to fix your reverse proxy's configuration or "
            + "Taguette's BASE_PATH setting.\n"
        ).format(self.application.config['BASE_PATH']))


class Login(BaseHandler):
    @PROM_REQUESTS.sync('login')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if self.current_user:
            return self._go_to_next()
        else:
            return self.render('login.html', register=False,
                               next=self.get_argument('next', ''))

    @PROM_REQUESTS.sync('login')
    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        login = self.get_body_argument('login')
        try:
            login = validate.user_login(login)
        except validate.InvalidFormat:
            logger.info("Login: invalid login")
        else:
            password = self.get_body_argument('password')
            user = self.db.query(database.User).get(login)
            if user is None:
                logger.info("Login: non-existent user")
            elif not user.check_password(password):
                logger.info("Login: invalid password for %r", user.login)
            else:
                self.login(user.login)
                return self._go_to_next()

        return self.render(
            'login.html', register=False,
            next=self.get_argument('next', ''),
            login_error=self.gettext("Invalid login or password"),
        )

    def _go_to_next(self):
        next_ = self.get_argument('next', '')
        if not next_:
            next_ = self.reverse_url('index')
        return self.redirect(next_)


class Logout(BaseHandler):
    @PROM_REQUESTS.sync('logout')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        self.logout()
        return self.redirect(self.reverse_url('index'))


class Register(BaseHandler):
    @PROM_REQUESTS.sync('register')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        if self.current_user:
            return self.redirect(self.reverse_url('index'))
        else:
            return self.render('login.html', register=True)

    @PROM_REQUESTS.sync('register')
    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        if not self.application.config['REGISTRATION_ENABLED']:
            raise HTTPError(403)
        try:
            login = self.get_body_argument('login')
            password1 = self.get_body_argument('password1')
            password2 = self.get_body_argument('password2')
            login = validate.user_login(login, new=True)
            validate.user_password(password1)
            email = self.get_body_argument('email', '')
            if email:
                validate.user_email(email)
            if password1 != password2:
                raise validate.InvalidFormat(_f("Passwords do not match"))
            if self.db.query(database.User).get(login) is not None:
                raise validate.InvalidFormat(_f("User name is taken"))
            if (
                email and
                self.db.query(database.User)
                    .filter(database.User.email == email)
                    .count() > 0
            ):
                raise validate.InvalidFormat(_f("Email address is already "
                                                "used"))
            user = database.User(login=login)
            user.set_password(password1)
            if email:
                user.email = email
            if (
                self.application.terms_of_service is not None
                and self.get_body_argument('tos', None) != 'accepted'
            ):
                raise validate.InvalidFormat(_f(
                    "Terms of Service must be accepted",
                ))
            self.db.add(user)
            self.db.commit()
            logger.info("User registered: %r", login)
            self.set_secure_cookie('user', login)
            return self.redirect(self.reverse_url('index'))
        except validate.InvalidFormat as e:
            logger.info("Error validating Register: %r", e)
            return self.render('login.html', register=True,
                               register_error=self.gettext(e.message))


class TermsOfService(BaseHandler):
    @PROM_REQUESTS.sync('tos')
    def get(self):
        if self.application.terms_of_service:
            return self.render(
                'tos.html',
                tos_text=Markup(self.application.terms_of_service),
            )
        else:
            raise HTTPError(404)


class Account(BaseHandler):
    def get_languages(self):
        return [
            (loc_code, tornado.locale.get(loc_code).name)
            for loc_code in tornado.locale.get_supported_locales()
        ]

    @authenticated
    @PROM_REQUESTS.sync('account')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        user = self.db.query(database.User).get(self.current_user)
        if user is None:
            logger.warning("User is logged in as non-existent user %r",
                           self.current_user)
            self.logout()
            raise HTTPError(403)
        return self.render('account.html', user=user,
                           languages=self.get_languages(),
                           current_language=user.language)

    @authenticated
    @PROM_REQUESTS.sync('account')
    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        user = self.db.query(database.User).get(self.current_user)
        if user is None:
            logger.warning("User is logged in as non-existent user %r",
                           self.current_user)
            self.logout()
            raise HTTPError(403)
        try:
            email = self.get_body_argument('email', None)
            language = self.get_body_argument('language', None)
            password1 = self.get_body_argument('password1', None)
            password2 = self.get_body_argument('password2', None)
            if email is not None:
                if email:
                    validate.user_email(email)
                user.email = email or None
            if password1 or password2:
                validate.user_password(password1)
                if password1 != password2:
                    raise validate.InvalidFormat(_f("Passwords do not match"))
                user.set_password(password1)
            if language not in tornado.locale.get_supported_locales():
                language = None
            user.language = language
            if language is None:
                self.clear_cookie('language')
            else:
                self.set_secure_cookie('language', language)
            self.db.commit()
            return self.redirect(self.reverse_url('account'))
        except validate.InvalidFormat as e:
            logger.info("Error validating Account: %r", e)
            return self.render('account.html', user=user,
                               languages=self.get_languages(),
                               current_language=user.language,
                               error=self.gettext(e.message))


class AskResetPassword(BaseHandler):
    @PROM_REQUESTS.sync('reset_password')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        return self.render('reset_password.html')

    @PROM_REQUESTS.async_('reset_password')
    async def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        email = self.get_body_argument('email')
        user = (
            self.db.query(database.User).filter(database.User.email == email)
        ).one_or_none()
        if user is None:
            return await self.render(
                'reset_password.html',
                error=self.gettext("This email address is not associated with "
                                   "any user"),
            )
        elif (
            user.email_sent is None
            or user.email_sent + timedelta(days=1) < datetime.utcnow()
        ):
            # Generate a signed token
            reset_token = '%s|%s|%s' % (
                int(time.time()),
                user.login,
                user.email,
            )
            reset_token = self.create_signed_value('reset_token', reset_token)
            reset_token = reset_token.decode('utf-8')

            # Reset link
            path = self.request.path
            if path.endswith('/reset_password'):
                path = path[:-15]
            path = path + '/new_password'
            reset_link = urlunparse(['https',
                                     self.request.host,
                                     path,
                                     '',
                                     'reset_token=' + reset_token,
                                     ''])

            msg = EmailMessage()
            msg['Subject'] = self.gettext("Password reset for Taguette")
            msg['From'] = self.application.config['EMAIL']
            msg['To'] = "{} <{}>".format(user.login, user.email)
            msg.set_content(self.render_string(
                'email_reset_password.txt',
                link=reset_link,
                login=user.login,
            ))
            msg.add_alternative(
                self.render_string(
                    'email_reset_password.html',
                    link=reset_link,
                    login=user.login,
                ),
                subtype='html',
            )

            logger.warning("Sending reset password email to %s %s",
                           user.login, user.email)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.application.send_mail(msg),
            )
            user.email_sent = datetime.utcnow()
            self.db.commit()
        else:
            logger.warning(
                "NOT Sending reset password email to %s %s (rate limited)",
                user.login, user.email,
            )
        return await self.render('reset_password.html', message="Email sent!")


class SetNewPassword(BaseHandler):
    def decode_reset_token(self, reset_token):
        reset_token_clear = self.get_secure_cookie(
            'reset_token',
            reset_token,
            min_version=2,
            max_age_days=1,
        )
        if reset_token_clear is None:
            raise HTTPError(403, _f("Invalid token"))
        ts, login, email = reset_token_clear.decode('utf-8').split('|', 2)
        user = self.db.query(database.User).get(login)
        if not user or user.email != email:
            raise HTTPError(403, _f("No user associated with that token"))
        if user.password_set_date >= datetime.utcfromtimestamp(int(ts)):
            # Password has been changed after the reset token was created
            raise HTTPError(403, _f("Password has already been changed"))
        return user

    @PROM_REQUESTS.sync('new_password')
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        reset_token = self.get_query_argument('reset_token')
        try:
            self.decode_reset_token(reset_token)
        except HTTPError as e:
            self.set_status(403)
            return self.render(
                'login.html', register=False,
                login_error=self.gettext(e.log_message),
            )
        return self.render('new_password.html', reset_token=reset_token)

    @PROM_REQUESTS.sync('new_password')
    def post(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        reset_token = self.get_body_argument('reset_token')
        try:
            user = self.decode_reset_token(reset_token)
        except HTTPError as e:
            self.set_status(403)
            return self.render(
                'login.html', register=False,
                login_error=self.gettext(e.log_message),
            )
        try:
            password1 = self.get_body_argument('password1')
            password2 = self.get_body_argument('password2')
            validate.user_password(password1)
            if password1 != password2:
                raise validate.InvalidFormat(_f("Passwords do not match"))
            logger.info("Password reset: changing password for %r", user.login)
            user.set_password(password1)
            self.db.commit()
            return self.redirect(self.reverse_url('index'))
        except validate.InvalidFormat as e:
            logger.info("Error validating SetNewPassword: %r", e)
            return self.render('new_password.html', reset_token=reset_token,
                               error=self.gettext(e.message))


class ProjectAdd(BaseHandler):
    @authenticated
    @PROM_REQUESTS.sync('new_project')
    def get(self):
        return self.render('project_new.html')

    @authenticated
    @PROM_REQUESTS.sync('new_project')
    def post(self):
        name = self.get_body_argument('name', '')
        description = self.get_body_argument('description', '')
        try:
            validate.project_name(name)
            validate.description(description)

            # Create project
            project = database.Project(name=name, description=description)
            self.db.add(project)
            # Add user as admin
            membership = database.ProjectMember(
                project=project,
                user_login=self.current_user,
                privileges=database.Privileges.ADMIN
            )
            self.db.add(membership)
            # Add default tags
            self.db.add(database.Tag(
                project=project,
                # TRANSLATORS: Default tag name
                path=self.gettext("interesting"),
                # TRANSLATORS: Default tag description
                description=self.gettext("Further review required")),
            )

            self.db.commit()
            return self.redirect(self.reverse_url('project', project.id))
        except validate.InvalidFormat as e:
            logger.info("Error validating ProjectAdd: %r", e)
            return self.render('project_new.html',
                               name=name, description=description,
                               error=self.gettext(e.message))

    def render(self, template_name, **kwargs):
        for name in ('name', 'description', 'error'):
            kwargs.setdefault(name, '')
        super(ProjectAdd, self).render(template_name, **kwargs)


class ProjectImport(BaseHandler):
    def prepare(self):
        if not self.application.config['SQLITE3_IMPORT_ENABLED']:
            raise HTTPError(403)

    @authenticated
    @PROM_REQUESTS.sync('import_project')
    def get(self):
        return self.render('project_import.html')


class ProjectDelete(BaseHandler):
    @authenticated
    @PROM_REQUESTS.sync('delete_project')
    def get(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_project():
            self.set_status(403)
            return self.finish(self.gettext(
                "You don't have permission to delete this project",
            ))
        doc = aliased(database.Document)
        highlights = (
            self.db.query(database.Highlight)
            .join(doc, database.Highlight.document_id == doc.id)
            .filter(doc.project_id == project.id)
        ).count()
        return self.render('project_delete.html', project=project,
                           documents=len(project.documents),
                           tags=len(project.tags),
                           highlights=highlights)

    @authenticated
    @PROM_REQUESTS.sync('delete_project')
    def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_delete_project():
            raise HTTPError(403)
        logger.warning("Deleting project %d %r user=%r",
                       project.id, project.name, self.current_user)
        self.db.delete(project)
        self.db.commit()
        return self.redirect(self.reverse_url('index'))


class ImportCodebook(BaseHandler):
    @authenticated
    @PROM_REQUESTS.sync('import_codebook')
    def get(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_import_codebook():
            self.set_status(403)
            return self.finish(self.gettext(
                "You don't have permission to import a codebook",
            ))
        return self.render('project_import_codebook.html', project=project)

    def _show_confirmation_form(self, project, tags, errors=[]):
        # Load tags from project, to set whether they exist
        project_tags = set(tag.path for tag in project.tags)
        for tag in tags:
            tag['exists'] = tag['path'] in project_tags

        return self.render(
            'project_import_codebook_confirm.html',
            project=project,
            tags=tags,
            errors=errors,
        )

    @authenticated
    @PROM_REQUESTS.sync('import_codebook')
    def post(self, project_id):
        project, privileges = self.get_project(project_id)
        if not privileges.can_import_codebook():
            self.set_status(403)
            return self.render(
                'project_import_codebook.html',
                project=project,
                error=self.gettext(
                    "You don't have permission to import a codebook",
                ),
            )

        if 'file' in self.request.files and len(self.request.files) >= 1:
            uploaded_file = self.request.files['file'][0]

            reader = io.BytesIO(uploaded_file.body)
            try:
                tags = import_codebook.list_tags(reader)
            except import_codebook.InvalidCodebook as e:
                msg = self.gettext(e.message)
                if e.row is not None:
                    msg = self.gettext("Row %d: %s") % (e.row, msg)
                self.set_status(400)
                return self.render(
                    'project_import_codebook.html',
                    project=project,
                    error=msg,
                )

            # Disable duplicates
            seen_paths = set()
            for tag in tags:
                tag['enabled'] = tag['path'] not in seen_paths
                seen_paths.add(tag['path'])

            # Sort by path, keeping the enabled one first
            tags = sorted(tags, key=lambda t: (t['path'], not t['enabled']))

            return self._show_confirmation_form(project, tags)
        elif self.get_body_argument('tag0-path', None):
            # Accumulate validation errors
            errors = []
            # What to insert/update into database
            replace_tags = {}
            insert_tags = []
            # List of tags to show the confirmation form again on conflict
            tags = []

            for i in itertools.count():
                path = self.get_body_argument('tag%d-path' % i, None)
                description = self.get_body_argument(
                    'tag%d-description' % i,
                    '',
                )
                if path is None:
                    break

                replace = enabled = True
                if self.get_body_argument('tag%d-replace' % i, ''):
                    replace = True
                elif self.get_body_argument('tag%d-import' % i, ''):
                    replace = False
                else:
                    enabled = False

                try:
                    validate.tag_path(path)
                    validate.description(description)
                except validate.InvalidFormat as e:
                    errors.append(self.gettext(e.message))
                    continue

                tags.append({
                    'path': path,
                    'description': description,
                    'enabled': enabled,
                })
                if not enabled:
                    continue

                if replace:
                    replace_tags[path] = {'description': description}
                else:  # Insert
                    insert_tags.append({
                        'path': path,
                        'description': description,
                    })

            if errors:
                self.set_status(400)
                return self.render(
                    'project_import_codebook_confirm.html',
                    project=project,
                    errors=errors,
                )

            try:
                changed_tags = []

                # Do updates
                for tag in project.tags:
                    try:
                        tag_update = replace_tags.pop(tag.path)
                    except KeyError:
                        pass
                    else:
                        tag.description = tag_update['description']
                        changed_tags.append(tag)
                if replace_tags:
                    raise KeyError

                # Do inserts
                for tag_insert in insert_tags:
                    tag = database.Tag(
                        project_id=project.id,
                        path=tag_insert['path'],
                        description=tag_insert['description'],
                    )
                    self.db.add(tag)
                    changed_tags.append(tag)

                self.db.flush()
                commands = []
                for tag in changed_tags:
                    cmd = database.Command.tag_add(
                        self.current_user,
                        tag,
                    )
                    self.db.add(cmd)
                    commands.append(cmd)
                self.db.flush()

                self.db.commit()
                for cmd in commands:
                    self.application.notify_project(project.id, cmd)
                return self.redirect(self.reverse_url('project', project.id))
            except (IntegrityError, KeyError):
                logger.warning("Error importing codebook", exc_info=True)
                self.db.rollback()
                error = self.gettext(
                    "Error importing tags, concurrent changes caused a "
                    + "conflict",
                )
                self.set_status(409)
                return self._show_confirmation_form(
                    project,
                    tags,
                    errors=[error],
                )
        else:
            self.set_status(400)
            return self.render(
                'project_import_codebook.html',
                project=project,
                error=self.gettext("No file provided"),
            )


class Project(BaseHandler):
    @authenticated
    @PROM_REQUESTS.sync('project')
    def get(self, project_id):
        project, privileges = self.get_project(project_id)
        documents_json = Markup(json.dumps(
            {
                str(doc.id): {'id': doc.id, 'name': doc.name,
                              'description': doc.description,
                              'text_direction': doc.text_direction.name}
                for doc in project.documents
            },
            sort_keys=True,
        ))
        tags_json = Markup(json.dumps(
            {
                str(tag.id): {'id': tag.id,
                              'path': tag.path,
                              'description': tag.description,
                              'count': tag.highlights_count}
                for tag in project.tags
            },
            sort_keys=True,
        ))
        members = (
            self.db.query(database.ProjectMember)
            .filter(database.ProjectMember.project_id == project_id)
        ).all()
        can_import_codebook = privileges.can_import_codebook()
        can_delete_project = privileges.can_delete_project()
        members_json = Markup(json.dumps(
            {member.user_login: {'privileges': member.privileges.name}
             for member in members}
        ))
        _ = self.xsrf_token  # Make sure XSRF cookie is set
        return self.render(
            'project.html',
            project=project,
            last_event=(project.last_event
                        if project.last_event is not None
                        else -1),
            documents=documents_json,
            user_login=Markup(
                json.dumps(self.current_user)
            ),
            tags=tags_json,
            members=members_json,
            can_import_codebook=can_import_codebook,
            can_delete_project=can_delete_project,
        )
