import logging

from tornado.escape import url_escape
from tornado.web import RequestHandler

from . import database


logger = logging.getLogger(__name__)


class AuthHandler(RequestHandler):
    def get_current_user(self):
        cookie = self.get_secure_cookie('user')
        if cookie is None:
            return None
        try:
            cookie = cookie.decode('utf-8')
        except ValueError:
            logger.warning("Cookie is invalid UTF-8")
            return None
        user = self.db.query(database.User).get(cookie)
        return user

    def login(self, username):
        self.set_secure_cookie('user', username)

    def redirect_if_not_logged_in(self):
        if self.current_user is None:
            self.redirect('/login?back=%s' % url_escape(self.request.path))
            return True
        return False
