import os
import tornado.ioloop
import tornado.web

from .login import AuthHandler
from . import models


database = models.connect()


class BaseHandler(AuthHandler):
    """Base class for all request handlers.
    """


class IndexHandler(BaseHandler):
    """Index page, shows welcome message and user's projects.
    """
    def get(self):
        self.render('index.html', message="Hello, world")


app = tornado.web.Application(
    [
        ('/', IndexHandler, {'logged_in_only': False}),
        (r'/static/(.*)', tornado.web.StaticFileHandler, {
            'path': os.path.join(os.path.dirname(__file__), 'static')
        }),
    ],
    template_path=os.path.join(os.path.dirname(__file__), 'templates'),
    debug=True,
)


if __name__ == '__main__':
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()
