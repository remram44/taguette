Changelog
=========

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
