Taguette website
================

This is the Taguette website, https://www.taguette.org. We made this using [Material for MkDocs](https://squidfunk.github.io/mkdocs-material).

Local development
-----------------

You can build the website locally, which will allow you to test things out and see your changes:

1. Clone this git repository from the terminal: ``git clone --branch website https://gitlab.com/remram44/taguette.git taguette-website``
2. Navigate on the command line to the repository you've just cloned locally, using the ``cd`` command. It should look like ``cd taguette``
3. Create a [virtual environment](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/#installing-virtualenv): ``python3 -m virtualenv taguette-website.venv`` and activate it using ``source taguette-website.venv/bin/activate``
4. Install the dependencies by running ``pip install -r requirements.txt``
6. Build the website using ``mkdocs build``
7. Run and view the website by using ``mkdocs serve``
