#!/usr/bin/env python3
import gettext
import glob
import jinja2
import logging
import os
import sys


logger = logging.getLogger('generate')


class TranslationWrapper(object):
    def __init__(self, trans):
        self._trans = trans

    def gettext(self, message, **kwargs):
        message = self._trans.gettext(message)
        if kwargs:
            message = message % kwargs
        return message

    def ngettext(self, singular, plural, n, **kwargs):
        message = self._trans.ngettext(singular, plural, n)
        if kwargs:
            message = message % kwargs
        return message


def main():
    logging.basicConfig(level=logging.INFO)

    out = sys.argv[1]

    # Initialize templates
    template_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(['.']),
        autoescape=jinja2.select_autoescape(['html']),
        extensions=['jinja2.ext.i18n'],
    )

    # List languages
    languages = [None]
    for locale in os.listdir('l10n'):
        if os.path.exists(os.path.join(
            'l10n', locale,
            'LC_MESSAGES', 'taguette_website.mo',
        )):
            languages.append(locale)

    for language in languages:
        logger.info(
            "Language: %s",
            language if language is not None else "(original English)",
        )

        if language is None:
            out_dir = out

            trans = gettext.NullTranslations()
        else:
            out_dir = os.path.join(out, language.split('_', 1)[0])
            try:
                os.mkdir(out_dir)
            except FileExistsError:
                pass

            trans = gettext.translation('taguette_website', 'l10n', [language])

        trans = TranslationWrapper(trans)

        # Render pages
        for page in glob.glob('*.html'):
            if page.startswith('_'):
                continue
            logger.info("Rendering %s...", page)
            template = template_env.get_template(page)
            with open(os.path.join(out_dir, page), 'w') as f_out:
                f_out.write(template.render(
                    gettext=trans.gettext,
                    ngettext=trans.ngettext,
                ))


if __name__ == '__main__':
    main()
