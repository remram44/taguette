Changelog
=========

0.5 (2019-03-23)
----------------

Bugfixes:
* Improve reading of OPF output from Calibre, which might fix compatibility with some combinations of Calibre versions and input formats
* Long tag names no longer stick out of the left pane
* Sort tags in highlight modal, documents in left pane, highlights and their tags in the highlights view

Features:
* Use a configuration file in server mode, rather than a growing list of command-line options
* Expose metrics to Prometheus
* Send errors to Sentry
* Add 'delete project' button
* Add account management page, to update email/password
* Add password recovery feature (if you have an email set)
* "New highlight" button shows up next to selected text rather than mouse, making it work with touch screens (mobile) and screen readers (hopefully)
* Convert old .DOC files (Word 97) using WV if available
* Add collaborator management modal, to add more members to a project
* Changed default port number from `8000` to `7465`
* Add spinning icon while requests are in progress, to prevent multiple submission of forms (document add takes ~10s for example)

0.4.4 (2018-11-29)
------------------

Bugfixes:
* Fix error creating a highlight when a paragraph is selected to the end
* Correctly handle Calibre sometimes writing a `.xhtml` file instead of `.html`
* Also show highlights with no tags when selecting "See all highlights"

0.4.3 (2018-11-17)
------------------

Bugfixes:
* Fix JavaScript error on a brand new project (no recorded Command)
* Fix Commands being sent to the wrong project

Features:
* Add `--xheaders` option for the hosted setup, showing correct IPs in the log
* Show which document in the list is the current one

0.4.2 (2018-11-15)
------------------

Bugfixes:
* Don't show highlights from a different document
* Handle non-ascii text better
* Fix real-time updates pausing if two changes happen in the same second
* Add messages boxes to signal when something goes wrong
* Sanitize name of uploaded files

0.4.1 (2018-11-12)
------------------

Bugfixes:
* Log errors from async handlers to the console instead of hiding them
* Work around a problem computing highlight positions in documents when unicode is present (won't crash anymore, but positions might still be off, fix to come)
* Fix not being able to create tags with names that collide with tags in other projects, and error creating a project if another project still uses default tags
* Fix exporting a document that has 0 highlights
* Fix document export missing highlights
* Fix navbar expand button (shown on smaller screen sizes) not working

0.4 (2018-11-11)
----------------

Bugfixes:
* Make sure to hide auth token from URL bar
* Fix tag description not showing up
* Don't allow two tags to have the same name

Features:
* Add confirmation dialogs before deleting tags or documents
* Create tag from the highlight window
* New theme matching website (thanks to Vicky Steeves)
* Add button to create a tag from the highlight modal
* Show messages from taguette.fr, such as new version available
* Add export options, allowing you to get your highlights or highlighted documents as HTML, DOCX, or PDF
* Add HTML and PDF options for codebook export as well
* Add an option to show (or export) all highlights, rather than only a specific tag

0.3 (2018-10-29)
----------------

Bugfixes:
* Fix having to reload for changes to appear when working on project other than 1.
* Fix tags not being sorted by name

Features:
* Add 'backlight' mode, fading non-tagged text
* Add modal dialog to edit and delete documents
* Add migration system, to automatically upgrade the database to new schema version when required

0.2 (2018-10-21)
----------------

Bugfixes:
* Accept list and numbered lists, as generated from Markdown documents
* Fix tag modal not able to add tags after a tag has been edited

Features:
* Add single-user mode, the default. Multi-user mode now needs `--multiuser`
* Add login and registration pages
* Add codebook export to CSV and DOCX files (contains list of tags with their descriptions)

0.1 (2018-10-21)
----------------

First version, proof of concept. Not very useful, but showcases the app, and can be installed by alpha testers.

* Can create projects
* Can import documents into the database as HTML
* Uses Calibre to convert supported documents into HTML
* Can highlight parts of documents, and assign tags
* Real-time notifications and collaboration
* "Acceptable" UI with bootstrap
