import gettext
import json
import logging
from markupsafe import Markup
import pkg_resources
from tornado.routing import URLSpec
from tornado.web import HTTPError

from .. import database
from .base import Application, BaseHandler
from . import api, export, views


logger = logging.getLogger(__name__)


class RedirectAccount(BaseHandler):
    def get(self):
        if not self.application.config['MULTIUSER']:
            raise HTTPError(404)
        return self.redirect(self.reverse_url('account'), True)


class TranslationJs(BaseHandler):
    def get(self):
        catalog = {}

        d = pkg_resources.resource_filename('taguette', 'l10n')
        gettext_trans = gettext.translation('taguette_javascript', d,
                                            [self.locale.code], fallback=True)
        if gettext_trans is not None:
            if isinstance(gettext_trans, gettext.GNUTranslations):
                catalog = gettext_trans._catalog

        language = Markup(json.dumps(self.locale.code))
        catalog = Markup(json.dumps(catalog))
        self.set_header('Content-Type', 'text/javascript')
        return self.render('trans.js',
                           language=language,
                           catalog=catalog)


class MessagesJs(BaseHandler):
    async def get(self):
        if not self.application.messages_event.is_set():
            await self.application.messages_event.wait()
        messages = json.dumps(self.application.messages)
        self.set_header('Content-Type', 'text/javascript')
        return await self.render('messages.js',
                                 messages=Markup(messages))


class Error404(BaseHandler):
    def initialize(self):
        self.set_status(404)

    def prepare(self):
        self.render(
            'error.html',
            error_title=self.pgettext("page title", "Error 404"),
            error_message=self.gettext("This page does not exist."),
        )
        raise HTTPError(404)


class Health(BaseHandler):
    @views.PROM_REQUESTS.sync('health')
    def get(self):
        self.set_header('Content-Type', 'text/plain')

        if self.application.is_exiting:
            self.set_status(503, "Shutting down")
            return self.finish("Shutting down")

        try:
            self.db.query(database.Project).first()
        except Exception:
            self.set_status(503)
            return self.finish("Database unavailable")

        return self.finish("Ok")


class UnbakedURLSpec(object):
    def __init__(self, pattern, handler, kwargs=None, name=None):
        self.pattern = pattern
        self.handler = handler
        self.kwargs = kwargs
        self.name = name

    def bake(self, *, base_path):
        return URLSpec(
            base_path + self.pattern,
            self.handler,
            kwargs=self.kwargs,
            name=self.name,
        )


def make_app(config, debug=False, xsrf_cookies=True):
    routes = [
        # Basic pages
        UnbakedURLSpec('/', views.Index, name='index'),
        UnbakedURLSpec('/cookies', views.CookiesPrompt, name='cookies_prompt'),
        UnbakedURLSpec('/login', views.Login, name='login'),
        UnbakedURLSpec('/logout', views.Logout, name='logout'),
        UnbakedURLSpec('/register', views.Register, name='register'),
        UnbakedURLSpec('/tos', views.TermsOfService, name='tos'),
        UnbakedURLSpec('/account', views.Account, name='account'),
        UnbakedURLSpec('/reset_password', views.AskResetPassword,
                       name='reset_password'),
        UnbakedURLSpec('/new_password', views.SetNewPassword,
                       name='new_password'),
        UnbakedURLSpec('/project/new', views.ProjectAdd, name='new_project'),
        UnbakedURLSpec('/project/import', views.ProjectImport,
                       name='import_project'),
        UnbakedURLSpec('/project/([0-9]+)/delete', views.ProjectDelete,
                       name='delete_project'),
        UnbakedURLSpec('/project/([0-9]+)/import_codebook',
                       views.ImportCodebook,
                       name='import_codebook'),

        # Project view
        UnbakedURLSpec('/project/([0-9]+)', views.Project, name='project'),
        UnbakedURLSpec('/project/([0-9]+)/document/[0-9]+', views.Project,
                       name='project_doc'),
        UnbakedURLSpec('/project/([0-9]+)/highlights/.*', views.Project,
                       name='project_tag'),

        # Export options
        UnbakedURLSpec('/project/([0-9]+)/export/project\\.sqlite3',
                       export.ExportSqlite, name='export_project_sqlite'),
        UnbakedURLSpec('/project/([0-9]+)/export/codebook\\.qdc',
                       export.ExportCodebookXml, name='export_codebook_qdc'),
        UnbakedURLSpec('/project/([0-9]+)/export/codebook\\.csv',
                       export.ExportCodebookCsv, name='export_codebook_csv'),
        UnbakedURLSpec('/project/([0-9]+)/export/codebook\\.xlsx',
                       export.ExportCodebookXlsx, name='export_codebook_xlsx'),
        UnbakedURLSpec('/project/([0-9]+)/export/codebook\\.([a-z0-3]{2,4})',
                       export.ExportCodebookDoc, name='export_codebook_doc'),
        UnbakedURLSpec('/project/([0-9]+)/export/document/'
                       '([^/]+)\\.([a-z0-9]{2,4})',
                       export.ExportDocument, name='export_document'),
        UnbakedURLSpec('/project/([0-9]+)/export/highlights/(.*)\\.csv',
                       export.ExportHighlightsCsv),
        UnbakedURLSpec('/project/([0-9]+)/export/highlights/(.*)\\.xlsx',
                       export.ExportHighlightsXlsx),
        UnbakedURLSpec('/project/([0-9]+)/export/highlights/'
                       '(.*)\\.([a-z0-3]{2,4})',
                       export.ExportHighlightsDoc,
                       name='export_highlights_doc'),

        # API
        UnbakedURLSpec('/api/check_user', api.CheckUser),
        UnbakedURLSpec('/api/import', api.ProjectImport),
        UnbakedURLSpec('/api/project/([0-9]+)', api.ProjectMeta),
        UnbakedURLSpec('/api/project/([0-9]+)/document/new', api.DocumentAdd),
        UnbakedURLSpec('/api/project/([0-9]+)/document/([0-9]+)',
                       api.Document),
        UnbakedURLSpec('/api/project/([0-9]+)/document/([0-9]+)/contents',
                       api.DocumentContents),
        UnbakedURLSpec('/api/project/([0-9]+)/document/([0-9]+)/highlight/new',
                       api.HighlightAdd),
        UnbakedURLSpec(
            '/api/project/([0-9]+)/document/([0-9]+)/highlight/([0-9]+)',
            api.HighlightUpdate),
        UnbakedURLSpec('/api/project/([0-9]+)/highlights/(.*)',
                       api.Highlights),
        UnbakedURLSpec('/api/project/([0-9]+)/tag/new', api.TagAdd),
        UnbakedURLSpec('/api/project/([0-9]+)/tag/([0-9]+)', api.TagUpdate),
        UnbakedURLSpec('/api/project/([0-9]+)/tag/merge', api.TagMerge),
        UnbakedURLSpec('/api/project/([0-9]+)/members', api.MembersUpdate),
        UnbakedURLSpec('/api/project/([0-9]+)/events', api.ProjectEvents),

        # Translation catalog and functions
        UnbakedURLSpec('/trans\\.js', TranslationJs, name='trans.js'),

        # Messages
        URLSpec('/messages\\.js', MessagesJs, name='messages.js'),

        # Well-known URLs
        URLSpec('/\\.well-known/change-password', RedirectAccount),
        UnbakedURLSpec('/health', Health),
    ]

    base_path = config['BASE_PATH']
    routes = [
        spec.bake(base_path=base_path) if isinstance(spec, UnbakedURLSpec)
        else spec
        for spec in routes
    ]

    if base_path:
        routes.append(URLSpec('/', views.BrokenBasePath))

    return Application(
        routes,
        static_path=pkg_resources.resource_filename('taguette', 'static'),
        login_url=base_path + '/login',
        xsrf_cookies=xsrf_cookies,
        debug=debug,
        config=config,
        default_handler_class=Error404,
    )
