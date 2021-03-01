#!/usr/bin/env python3
import functools
import gettext
import glob
import jinja2
import logging
import os
import shutil
import subprocess
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


class PseudoTranslation(object):
    CHARS = {
        'A': '\u00c5', 'B': '\u0181', 'C': '\u00c7', 'D': '\u00d0',
        'E': '\u00c9', 'F': '\u0191', 'G': '\u011c', 'H': '\u0124',
        'I': '\u00ce', 'J': '\u0134', 'K': '\u0136', 'L': '\u013b',
        'M': '\u1e40', 'N': '\u00d1', 'O': '\u00d6', 'P': '\u00de',
        'Q': '\u01ea', 'R': '\u0154', 'S': '\u0160', 'T': '\u0162',
        'U': '\u00db', 'V': '\u1e7c', 'W': '\u0174', 'X': '\u1e8a',
        'Y': '\u00dd', 'Z': '\u017d', 'a': '\u00e5', 'b': '\u0180',
        'c': '\u00e7', 'd': '\u00f0', 'e': '\u00e9', 'f': '\u0192',
        'g': '\u011d', 'h': '\u0125', 'i': '\u00ee', 'j': '\u0135',
        'k': '\u0137', 'l': '\u013c', 'm': '\u0271', 'n': '\u00f1',
        'o': '\u00f6', 'p': '\u00fe', 'q': '\u01eb', 'r': '\u0155',
        's': '\u0161', 't': '\u0163', 'u': '\u00fb', 'v': '\u1e7d',
        'w': '\u0175', 'x': '\u1e8b', 'y': '\u00fd', 'z': '\u017e',
        ' ': '\u2003',
    }

    @functools.lru_cache()
    def mangle(self, text):
        out = []
        i = 0
        while i < len(text):
            if text[i] == '{' and text[i + 1] == '{':
                # Jinja2 variable
                j = i + 2
                while text[j] != '}':
                    j += 1
                j += 1
                out.append(text[i:j + 1])
                i = j
            elif text[i] == '%' and text[i + 1] == '(':
                # Python variable
                j = i + 2
                while text[j] != ')':
                    j += 1
                j += 1
                assert text[j] in 'srdf'
                out.append(text[i:j + 1])
                i = j
            elif text[i] == '<':
                # HTML tag
                j = i + 1
                while text[j] != '>':
                    j += 1
                out.append(text[i:j + 1])
                i = j
            else:
                out.append(self.CHARS.get(text[i], text[i]))
            i += 1

        return ''.join(out)

    def gettext(self, message, **kwargs):
        message = self.mangle(message)
        if kwargs:
            message = message % kwargs
        return '[%s]' % message

    def ngettext(self, singular, plural, n, **kwargs):
        message = self.mangle(plural)
        if kwargs:
            message = message % kwargs
        return '[%s (n=%d)]' % (message, n)


LANGUAGE_NAMES = {
    None: 'English',
    'fr': 'French',
    'qps-ploc': 'Pseudo-locale',
}


def main():
    logging.basicConfig(level=logging.INFO)

    # Build .mo files
    for filename in os.listdir('po'):
        if filename.startswith('website_') and filename.endswith('.po'):
            code = filename[8:-3]
            directory = os.path.join('l10n', code, 'LC_MESSAGES')
            os.makedirs(directory, exist_ok=True)
            subprocess.check_call([
                'pybabel',
                'compile',
                '-i',
                os.path.join('po', filename),
                '-o',
                os.path.join(directory, 'taguette_website.mo'),
            ])

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

    all_language_links = []
    for language in languages:
        if language is None:
            language_link = None
        else:
            language_link = language.split('_', 1)[0]
        all_language_links.append({
            'link': language_link,
            'name': LANGUAGE_NAMES[language_link],
        })

    for language in languages:
        logger.info(
            "Language: %s",
            language if language is not None else "(original English)",
        )

        if language is None:
            language_link = None
            out_dir = out

            if os.environ.get('TAGUETTE_TEST_LOCALE') == 'y':
                trans = PseudoTranslation()
            else:
                trans = gettext.NullTranslations()
        else:
            language_link = language.split('_', 1)[0]
            out_dir = os.path.join(out, language_link)
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
                    current_page_link='' if page == 'index.html' else page,
                    current_language={
                        'link': language_link,
                        'name': LANGUAGE_NAMES[language_link],
                    },
                    languages=all_language_links,
                    gettext=trans.gettext,
                    ngettext=trans.ngettext,
                ))

        # Copy static files
        for name in [
            'css', 'imgs', 'js', 'webfonts',
            'favicon.ico', 'robots.txt', 'sitemap.xml',
        ]:
            dest = os.path.join(out_dir, name)

            # Remove existing
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            elif os.path.exists(dest):
                os.remove(dest)

            # Copy
            if os.path.isdir(name):
                shutil.copytree(name, dest)
            else:
                shutil.copy2(name, dest)


if __name__ == '__main__':
    main()
