Taguette
========

A spin on the phrase "tag it!", `Taguette <https://www.taguette.org/>`__ is a free and open source qualitative research tool that allows users to:

+ Import PDFs, Word Docs (``.docx``), Text files (``.txt``), HTML, EPUB, MOBI, Open Documents (``.odt``), and Rich Text Files (``.rtf``).
+ Highlight words, sentences, or paragraphs and tag them with the codes *you* create.
+ (not yet) Group imported documents together (e.g. as 'Interview' or 'Lit Review').
+ Export tagged documents, highlights for a specific tag, a list of tags with descriptions and colors, and whole projects.

`Check out our website to learn more about how to install and get started. <https://www.taguette.org/>`__

Motivation and goal
-------------------

Qualitative methods generate rich, detailed research materials that leave individuals' perspectives intact as well as provide multiple contexts for understanding the phenomenon under study. Qualitative methods are used by a wide range of fields, such as anthropology, education, nursing, psychology, sociology, and marketing. Qualitative data has a similarly wide range: observations, interviews, documents, audiovisual materials, and more.

However - the software options for qualitative researchers are either **far too expensive**, don't allow for the seminal method of highlighting and tagging materials, *or actually perform quantitative analysis*, just on text.

**It's not right or fair that qualitative researchers without massive research funds cannot afford the basic software to do their research.**

So, to bolster a fair and equitable entry into qualitative methods, we've made Taguette!

Installation
------------

You can find complete installation instructions on `our website <https://www.taguette.org/install.html>`__, including installers for Windows and MacOS.

Development setup from the repository
-------------------------------------

You can install from a local clone of this repository, which will allow you to easily change the sources to suit your needs:

1. Clone this git repository from the terminal: ``git clone https://gitlab.com/remram44/taguette.git``
2. Navigate on the command line to the repository you've just cloned locally, using the ``cd`` command. To get help using ``cd``, use `this tutorial <https://swcarpentry.github.io/shell-novice/02-filedir/index.html>`__.
3. Taguette uses `Poetry <https://python-poetry.org/>`__ for its packaging and dependency management. You will need to `install Poetry <https://python-poetry.org/docs/#installation>`__.
4. Install Taguette and its dependencies by running ``poetry install``. Poetry will create a virtual environment for you by default, activate it by running ``poetry shell``.
5. Build translation files using ``scripts/update_translations.sh``.
6. You can start taguette in development mode using ``taguette --debug`` (or ``taguette --debug server <config_file>``). This will start Tornado in debug mode, which means in particular that it will auto-restart every time you make changes.
7. Navigate to `localhost:7465 <http://localhost:7465/>`__ to use Taguette!

License
-------

* Copyright (C) 2018, Rémi Rampin and Taguette contributors

Licensed under a **BSD 3-clause "New" or "Revised" License**. See the ``LICENSE.txt`` file for details.
