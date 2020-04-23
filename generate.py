import gettext
import glob
import jinja2
import logging
import os
import sys


logger = logging.getLogger('generate')


trans = gettext.NullTranslations()


def gettext(message, **kwargs):
    message = trans.gettext(message)
    if kwargs:
        message = message % kwargs
    return message


def ngettext(singular, plural, n, **kwargs):
    message = trans.ngettext(singular, plural, n)
    if kwargs:
        message = message % kwargs
    return message


def main():
    logging.basicConfig(level=logging.INFO)

    out = sys.argv[1]

    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(['.']),
        autoescape=jinja2.select_autoescape(['html']),
        extensions=['jinja2.ext.i18n'],
    )

    for page in glob.glob('*.html'):
        if page.startswith('_'):
            continue
        logger.info("Rendering %s...", page)
        template = template_env.get_template(page)
        with open(os.path.join(out, page), 'w') as f_out:
            f_out.write(template.render(
                gettext=gettext,
                ngettext=ngettext,
            ))


if __name__ == '__main__':
    main()
