Taguette website
================

This is the Taguette website, https://www.taguette.org/

Local development
-----------------

You can build the website locally, which will allow you to try out your changes:

1. Clone this git repository from the terminal: ``git clone --branch website https://gitlab.com/remram44/taguette.git taguette-website``
2. Navigate on the command line to the repository you've just cloned locally, using the ``cd`` command. To get help using ``cd``, use `this tutorial <https://swcarpentry.github.io/shell-novice/02-filedir/index.html>`__.
3. Taguette uses `Poetry <https://python-poetry.org/>`__ for its packaging and dependency management. You will need to `install Poetry <https://python-poetry.org/docs/#installation>`__.
4. Install the dependencies by running ``poetry install``. Poetry will create a virtual environment for you by default, activate it by running ``poetry shell``.
5. Create a directory to contain the built website
6. Build the website using ``python scripts/generate.py public/``
7. Open ``public/index.html`` to see the result
