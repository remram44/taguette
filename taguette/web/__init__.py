import os
import json
import logging
import pkg_resources
from tornado.routing import URLSpec

from .base import Application
from . import api, export, views


logger = logging.getLogger(__name__)


def make_app(config, debug=False):
    if 'XDG_CACHE_HOME' in os.environ:
        cache = os.environ['XDG_CACHE_HOME']
    else:
        cache = os.path.expanduser('~/.cache')
    os.makedirs(cache, 0o700, exist_ok=True)
    cache = os.path.join(cache, 'taguette.json')
    secret = None
    try:
        fp = open(cache)
    except IOError:
        pass
    else:
        try:
            secret = json.load(fp)['cookie_secret']
            fp.close()
        except Exception:
            logger.exception("Couldn't load cookie secret from cache file")
        if not isinstance(secret, str) or not 10 <= len(secret) < 2048:
            logger.error("Invalid cookie secret in cache file")
            secret = None
    if secret is None:
        secret = os.urandom(30).decode('iso-8859-15')
        try:
            fp = open(cache, 'w')
            json.dump({'cookie_secret': secret}, fp)
            fp.close()
        except IOError:
            logger.error("Couldn't open cache file, cookie secret won't be "
                         "persisted! Users will be logged out if you restart "
                         "the program.")

    return Application(
        [
            # Basic pages
            URLSpec('/', views.Index, name='index'),
            URLSpec('/login', views.Login, name='login'),
            URLSpec('/logout', views.Logout, name='logout'),
            URLSpec('/register', views.Register, name='register'),
            URLSpec('/project/new', views.ProjectAdd, name='new_project'),
            URLSpec('/project/([0-9]+)/delete', views.ProjectDelete,
                    name='delete_project'),

            # Project view
            URLSpec('/project/([0-9]+)', views.Project, name='project'),
            URLSpec('/project/([0-9]+)/document/[0-9]+', views.Project,
                    name='project_doc'),
            URLSpec('/project/([0-9]+)/highlights/[^/]*', views.Project,
                    name='project_tag'),

            # Export options
            URLSpec('/project/([0-9]+)/export/codebook.csv',
                    export.ExportCodebookCsv, name='export_codebook_csv'),
            URLSpec('/project/([0-9]+)/export/codebook.([a-z0-3]{2,4})',
                    export.ExportCodebookDoc, name='export_codebook_doc'),
            URLSpec('/project/([0-9]+)/export/document/'
                    '([^/]+)\\.([a-z0-9]{2,4})',
                    export.ExportDocument, name='export_document'),
            URLSpec('/project/([0-9]+)/export/highlights/'
                    '([^/]*)\\.([a-z0-3]{2,4})',
                    export.ExportHighlightsDoc, name='export_highlights_doc'),

            # API
            URLSpec('/api/project/([0-9]+)', api.ProjectMeta),
            URLSpec('/api/project/([0-9]+)/document/new', api.DocumentAdd),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)',
                    api.DocumentUpdate),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)/content',
                    api.DocumentContents),
            URLSpec('/api/project/([0-9]+)/document/([0-9]+)/highlight/new',
                    api.HighlightAdd),
            URLSpec(
                '/api/project/([0-9]+)/document/([0-9]+)/highlight/([0-9]+)',
                api.HighlightUpdate),
            URLSpec('/api/project/([0-9]+)/highlights/([^/]*)',
                    api.Highlights),
            URLSpec('/api/project/([0-9]+)/tag/new', api.TagAdd),
            URLSpec('/api/project/([0-9]+)/tag/([0-9]+)', api.TagUpdate),
            URLSpec('/api/project/([0-9]+)/events', api.ProjectEvents),
        ],
        static_path=pkg_resources.resource_filename('taguette', 'static'),
        login_url='/login',
        xsrf_cookies=True,
        debug=debug,
        config=config,
        cookie_secret=secret,
    )
