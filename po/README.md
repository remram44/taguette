Translating Taguette
====================

Taguette is being used globally. Therefore, it needs to be translatable into multiple languages.

What should be translated:

* All the text that is visible on web pages during normal usage (templates, messages, JavaScript messages)
* The messages printed to the terminal and the command-line help

What should NOT be translated:

* Logging and exception messages (those are really destined to developers)
* API messages and errors

There are two catalogs: `main` is used by the server, and `javascript` is loaded client-side as JSON to be used by the JavaScript code.

Run the script `scripts/update_translations.sh` before and after updating PO files. It will update the POT catalogs with the changes from the code and also generate the MO files from the translated PO files.

You will have to update your PO files from the POT files manually.

Standard mapping
================

This table intends to help standardize the terms used within a language translation, and between different languages.

| English   | French      |
| :-------- | :---------- |
| codebook  | *codebook*  |
| tag       | tag         |
| highlight | *marque*    |
| account   | profil      |
| settings  | préférences |
| email     | e-mail      |
