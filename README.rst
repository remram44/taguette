Taguette
========

A spin on the phrase "tag it!", `Taguette <http://taguette.fr/>`__ is a free and open source qualitative research tool that allows users to:

+ Import PDFs, Word Docs (``.docx``), Text files (``.txt``), HTML, EPUB, MOBI, Open Documents (``.odt``), and Rich Text Files (``.rtf``).
+ Highlight words, sentences, or paragraphs and tag them with the codes *you* create.
+ Group imported documents together (e.g. as 'Interview' or 'Lit Review').
+ Export tagged documents, highlights for a specific tag, a list of tags with description and colors, and whole projects.

To learn more about how to install and get started, keep reading!

Motivation and goal
-------------------

Qualitative methods generate rich, detailed research materials that leave individuals’ perspectives intact  as well as provide multiple contexts for understanding phenomenon under study. Qualitative methods are used by a wide range of fields, such as anthropology, education, nursing, psychology, sociology, and marketing. Qualitative data has a similarly wide range: observations, interviews, documents, audiovisual materials, and more.

However - the software options for qualitative researchers are either **far too expensive**, don't allow for the seminal method of highlighting and tagging materials, *or actually perform quantitative analysis*, just on text.

**It's not right or fair that qualitative researchers without massive research funds cannot afford the basic software to do their research.**

So, to bolster a fair and equitable entry into qualitative methods, we've made Taguette!

Installation
------------

**Pre-requisites**

To use Taguette right now, you first need to install `Python 3 <https://www.python.org/downloads/>`__ and `Calibre <https://calibre-ebook.com/>`__ , the open source e-book management software. Taguette uses a part of Calibre to convert uploaded documents into HTML, allowing you to highlight and tag parts of them. In the future, we hope to have a one-click installer for you. These instructions will work for Mac, Linux, and Windows.

Once you've installed Calibre, you can quickly install Taguette with it's dependencies from the command line with the following::

    pip install taguette

After which you can simply run ``taguette`` in the terminal to get it going. You'll see the command line will still be running. This is ok! Don't worry about the terminal but do leave it running. In your web browser, navigate to `localhost:8000 <http://localhost:8000/>`__ to begin working on your projects!

Otherwise, to install Taguette on your local computer, follow these steps:

1. Clone this git repository from the terminal: ``git clone https://gitlab.com/remram44/taguette.git``.
2. Navigate on the command line to the repository you've just cloned locally, using the ``cd`` command. To get help using ``cd``, use `this tutorial <https://swcarpentry.github.io/shell-novice/02-filedir/index.html>`__.
3. To install the dependencies of Taguette, run ``pip install .`` We recommend you run this inside of a `virtualenv or pipenv <https://docs.python-guide.org/dev/virtualenvs/>`__ if possible.
4. Once the dependencies have been installed, run ``taguette`` and you'll see the command line will still be running. This is ok! Don't worry about the terminal but do leave it running. In your web browser, navigate to `localhost:8000 <http://localhost:8000/>`__ to begin working on your projects!

Coming soon: installers for Mac and Windows!

Getting Started
---------------
After starting Taguette from the command line, navigate to `localhost:8000 <http://localhost:8000/>`__. You will see a page that greets you as the admin and has a button to **Start a new project**. Click that button and you'll be prompted to enter a **Title and Description** for your new project. This can be changed later on if you want.

Upon creating your project, you'll be taken the Project View, which has a left and a right pane. The left pane contains the information about your project information ('Project Info'), uploaded materials ('Documents'), and tags ('Highlights') as tabs. You can go between these tabs as you like. The right pane will render documents and be the area where you'll do the highlighting and tagging.

To get an idea of how to work in Taguette, let's upload a document and get you tagging! In the left pane, click on the 'Documents' tab. You should see a button that says **Upload a document**. Click that and pick either a ``.pdf``, ``.docx``, ``.txt``, or ``.odt`` file on your computer. Just one file to be uploaded. You'll be prompted to give the new document a Name (should be something human-readable, required) and Description (like a note about the file, optional). When you have picked a document and at least given it a name, click the **Import** button.

Once uploaded, you should see the document in the 'Documents' tab. Click on it and you should see the contents of your document in the right pane. Select some text by left-clicking and dragging it over the text you'd like to highlight.

Once you let go of your left-click, a pop-up that says **new highlight** will appear next to the highlighted text. Click that pop-up, and you will get a list of existing tags from which to choose. You can select one or more tags to apply to the highlight text.

Once you've checked off which tags you'd like to associate with the highlighted text, click **Save & Close**, and the text you've just tagged should now be highlighted with the color associated with the tag (e.g. bright yellow).

If you've accidentally tagged a section of text you didn't want to, you can delete it by clicking on the highlighted text. This will give you the same pop-up window that you used to tag it. Next to the save button, there is a grey button called **Delete**. Click that, and the tags will be removed from the text. It should no longer by highlighted.

Happy highlighting!


License
-------

* Copyright (C) 2018, Rémi Rampin

Licensed under a **BSD 3-clause "New" or "Revised" License**. See the `LICENSE <LICENSE.txt>`__ for details.
