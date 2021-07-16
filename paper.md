<!--
Preview this with https://whedon.theoj.org/
-->

---
title: 'Taguette: open source qualitative data analysis'
tags:
  - qualitative
  - qualitative data analysis
  - qual
  - document
  - text
  - tagging
  - tags
  - coding
  - highlights
  - notes
  - text-analysis
  - highlighting
  - caqdas
  - python
  - SQLite
authors:
  - name: Rémi Rampin
    orcid: 0000-0002-0524-2282
    affiliation: 1
  - name: Vicky Rampin
    orcid: 0000-0003-4298-168X
    affiliation: 1
affiliations:
 - name: Independent Researcher
   index: 1
date: 15 July 2021
bibliography: paper.bib
---

# Summary

Taguette[@Taguette] is an open source computer-assited qualitative data analysis software (CAQDAS) [@caqdas]. CAQDAS software help researchers using qualitative methods to organize, annotate, collaborate on, analyze, and visualize their work. Qualitative methods are used in a wide range of fields, such as anthropology, education, nursing, psychology, sociology, and marketing. Qualitative data has a similarly wide range: observations, interviews, documents, audiovisual materials, and more.

# Statement of Need

For commercial qualitative software, the lowest subscription price is $20/month, and the lowest desktop application price is $520 (MaxQDA). There have been fewer than twenty open source CAQDAS available **ever**, and fewer than five are being currently maintained, including Taguette.

It's not right or fair that qualitative researchers without massive research funds cannot afford the basic software to do their research. So, to bolster a fair and equitable entry into qualitative methods, we made Taguette.

# Taguette

Taguette is a web application written in Python. It is designed to run both on a desktop machine, in single-user mode, or on a server, where it allows real-time collaboration.

In addition, we have been running a server at [app.taguette.org](https://app.taguette.org/) for anyone to use since March 2019, where we have about 2,000 monthly active users.

Taguette is multiplatform, with installers provided for MacOS and Windows, a Docker image, and on the Python package Index (PyPI). It is available in 7 languages and has been downloaded over 12,000 times.

## Importing

Work in Taguette begins with importing a document. We support a variety of text formats, from HTML to RTF to EPUB, including PDF, DOCX, Markdown, etc. Documents are converted to HTML using the `ebook-convert` command, part of the Calibre ebook manager[@Calibre] or wvWare[@wvWave] for old Microsoft Word 97 `.doc` documents.

A copy of Calibre is included in our installers so that users don't have to set up any additional software. After conversion, the document is sanitized to remove unwanted formating and embedded media, and avoid security issues such as cross-site scripting.

## Exporting

Taguette offers a variety of exporting options. A user can export a codebook as a document or spreadsheet: the list of all the tags, with their description and the number of associated highlights throughout the project. Another option is to export a highlighted document, where the sections highlighted by the user are marked and each annotated with the associated tags. Finally, it is possible to export a list of all the highlights across documents, either for all tags or for a specific tag or hierarchy of tags.

It is also possible to export a project as a SQLite3 database, in Taguette's native schema, which contains all the information necessary to continue work on another instance of Taguette. It is even possible to import them on our hosted version, app.taguette.org, or to export from there to a local copy. Older versions of the schema are automatically recognized and converted to the latest version if needed.

## Live collaboration

The multi-user verison of Taguette allows for live collaboration of multiple users in a single project. It is possible to add other accounts as collaborators to your project, with a choice of permissions: some users can only tag, some can change documents, and others have full control including adding or removing collaborators.

From then on, any change made by a different user is reflected immediately for the other users. This allows for faster annotation of large projects, without having to exchange partially processed documents via email for example.

# Related Work

Other open-source CAQDAS packages include: QualCoder[@qualcoder], qcoder[@qcoder], and qdap[@qdap]. qcoder and qdap are both R packages, and require knowledge of R and RStudio to use. QualCoder has

# Acknowledgments

We thank Sarah whose qualitative work triggered the creation of Taguette. We would also like to thank our contributors on GitLab and our translators on Transifex, and the qualitative analysis community for their warm welcome and feedback.

In addition, we have recently started an [OpenCollective](https://opencollective.com/taguette) to support the development of Taguette, with the initial goal to cover the cost of a dedicated server for our hosted service.

# References
