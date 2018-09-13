import os
import tornado.ioloop
import tornado.web

from .auth import AuthHandler
from . import database


DBSession = database.connect()


class BaseHandler(AuthHandler):
    """Base class for all request handlers.
    """
    def __init__(self, application, request, **kwargs):
        super(BaseHandler, self).__init__(application, request, **kwargs)
        self.db = DBSession()


class IndexHandler(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    def get(self):
        return self.render('index.html', message="Hello, world")


class Login(BaseHandler):
    def get(self):
        self.login('remram')
        self.redirect(self.get_argument('back', '/'))


app = tornado.web.Application(
    [
        ('/', IndexHandler),
        ('/login', Login),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {
            'path': os.path.join(os.path.dirname(__file__), 'static')
        }),
    ],
    template_path=os.path.join(os.path.dirname(__file__), 'templates'),
    debug=True,
    cookie_secret='TODO:_cookie_here_',
)


if __name__ == '__main__':
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()
