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

The software is a web application which can be run both on a desktop machine, in single-user mode, or on a server, where it allows real-time collaboration. In addition, we have been running a server at [app.taguette.org](https://app.taguette.org/) for anyone to use since March 2019, where we have about 2,000 monthly users.

Taguette is multiplatform, with installers provided for MacOS and Windows, a Docker image, and on the Python package Index (PyPI). It is available in 7 languages.

# Statement of Need

For commercial qualitative software, the lowest subscription price is $20/month, and the lowest desktop application price is $520 (MaxQDA). There have been fewer than twenty open source CAQDAS available **ever**, and fewer than five are being currently maintained, including Taguette.

It's not right or fair that qualitative researchers without massive research funds cannot afford the basic software to do their research. So, to bolster a fair and equitable entry into qualitative methods, we made Taguette.

# TODO: Details?

* Web application written in Python
* Can be run either as a service, with user accounts, permissions, and live changes; or on a desktop machine, where it needs nothing else and will open a browser window (like Jupyter or OpenRefine)
* Supports Python 3.5-3.9
* Uses a SQL database that can easily be queried by other tools (SQLite3 by default, also tested with PostgreSQL and MariaDB)
* Exports coded documents, tags, highlights in a variety of formats (DOCX, PDF, CSV, XLSX, XML, and its own SQLite3 format)
* Can import project files (SQLite3) between instances and on the desktop version
* Can import a variety of formats thanks to the Calibre ebook manager, used to convert them to HTML
* Internationalized, currently translated in 7 languages: English, French, Brazilian Portuguese, German, Dutch, Italian, Spanish
* Available since October 2018, app.taguette.org running since March 2019
* Installers for MacOS and Windows, available on pypi.org

# Related Work

Other open-source CAQDAS packages include: QualCoder[@qualcoder], qcoder[@qcoder], and qdap[@qdap]. qcoder and qdap are both R packages, and require knowledge of R and RStudio to use. QualCoder has

# Acknowledgments

We thank Sarah whose qualitative work triggered the creation of Taguette. We would also like to thank our contributors on GitLab and our translators on Transifex, and the qualitative analysis community for their warm welcome and feedback.

# References
