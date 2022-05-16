import os
import string

from .utils import _f


class InvalidFormat(ValueError):
    """User-supplied value doesn't pass validation."""
    def __init__(self, message):
        super(InvalidFormat, self).__init__(message)
        self.message = message


def description(descr):
    if not isinstance(descr, str):
        raise ValueError("Description is not a string")
    if len(descr) > 102400:
        raise InvalidFormat(_f("Description is too long"))
    return True


def project_name(name):
    if not name:
        raise InvalidFormat(_f("Project name cannot be empty"))
    if len(name) > 50:
        raise InvalidFormat(_f("Project name is too long"))
    return True


ALLOWED_LOGIN_CHARACTERS_NEW = (
    string.ascii_lowercase + string.digits +
    '._-'
)
ALLOWED_LOGIN_CHARACTERS = (
    ALLOWED_LOGIN_CHARACTERS_NEW + '+@ '
)


def fix_user_login(login, *, new=False):
    login = login.lower()
    user_login(login, new=new)
    return login


def user_login(login, *, new=False):
    if not isinstance(login, str):
        raise ValueError("Login is not a string")
    if not login:
        raise InvalidFormat(_f("User login cannot be empty"))
    if len(login) > (20 if new else 25):
        raise InvalidFormat(_f("User login is too long"))
    if login != login.lower():
        raise InvalidFormat(_f("User login is not lowercase"))
    chars = ALLOWED_LOGIN_CHARACTERS_NEW if new else ALLOWED_LOGIN_CHARACTERS
    if any(c not in chars for c in login):
        raise InvalidFormat(_f("User login contains forbidden characters"))
    return True


def user_email(email):
    if not isinstance(email, str):
        raise ValueError("Email is not a string")
    if not email:
        raise InvalidFormat(_f("Email cannot be empty"))  # but it can be NULL
    if '@' not in email:
        raise InvalidFormat(_f("Invalid email address"))
    if len(email) > 256:
        raise InvalidFormat(_f("Email address is too long"))
    return True


def user_password(password):
    if not isinstance(password, str):
        raise ValueError("Password is not a string")
    if len(password) < 5:
        raise InvalidFormat(_f("Please use a longer password"))
    if len(password) > 5120:
        raise InvalidFormat(_f("Please use a shorter password"))
    return True


def document_name(name):
    if not isinstance(name, str):
        raise ValueError("Document name is not a string")
    if not name:
        raise InvalidFormat(_f("Document name cannot be empty"))
    if len(name) > 50:
        raise InvalidFormat(_f("Document name is too long"))
    return True


def tag_path(path):
    if not isinstance(path, str):
        raise ValueError("Tag path is not a string")
    if not path:
        raise InvalidFormat(_f("Tag path cannot be empty"))
    if len(path) > 200:
        raise InvalidFormat(_f("Tag path is too long"))
    return True


def filename(name):
    if not isinstance(name, str):
        raise ValueError("File name is not a string")
    if not name:
        raise ValueError("File name cannot be empty")
    if len(name) > 100:
        raise InvalidFormat(_f("File name is too long"))
    if '\x00' in name:
        raise InvalidFormat(_f("Invalid file name"))
    return True


def fix_filename(name):
    if not isinstance(name, str):
        raise ValueError("File name is not a string")
    if not name:
        raise ValueError("File name cannot be empty")
    if '/' in name:
        name = name[name.rindex('/') + 1:]
    if fix_filename.windows and '\\' in name:
        # It seems that IE gets that wrong, at least when the file is from
        # a network share
        name = name[name.rindex('\\') + 1:]
    name, ext = os.path.splitext(name)
    name = name[:50]
    ext = ext[:8]
    if not name:
        name = '_'
    name = name + ext
    return name


fix_filename.windows = os.name == 'nt'
