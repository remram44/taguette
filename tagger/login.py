from tornado.web import RequestHandler


class AuthHandler(RequestHandler):
    def initialize(self, logged_in_only, **kwargs):
        if logged_in_only:
            # TODO: check that we are logged in or redirect
            pass
        super(AuthHandler, self).initialize(**kwargs)
