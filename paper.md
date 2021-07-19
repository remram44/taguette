---
title: 'Taguette: open-source qualitative data analysis'
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
 - name:
   index: 1
date: 15 July 2021
bibliography: paper.bib
---

# Summary

Taguette is a free and open-source computer-assisted qualitative data analysis software (CAQDAS) [@caqdas]. CAQDAS software help researchers using qualitative methods to organize, annotate, collaborate on, analyze, and visualize their work. Qualitative methods are used in a wide range of fields, such as anthropology, education, nursing, psychology, sociology, and marketing. Qualitative data has a similarly wide range: interviews, focus groups, ethnographies, and more.

# Statement of Need

Taguette fills a specific research need for qualitative researchers who cannot afford access to the software to do their work. For commercial CAQDAS, the lowest subscription price is 20 USD/month, and the lowest desktop application price is 520 USD [@caqdas]. There have been fewer than twenty open-source CAQDAS available **ever**, and fewer than five are being currently maintained, including Taguette.

Taguette directly supports qualitative inquiry of text materials (see \autoref{fig:document}). It is unique in that it provides a free and open-source tool for qualitative researchers who want real-time collaboration (see \autoref{fig:collabs}). Taguette has already been used in multiple research publications, which we have compiled in a Zotero library [@taguette-zotero], and also is being self-hosted by research institutions on behalf of their communities (example: [Digitalization Research Cluster, Leiden University](https://taguette.leiden.digital/)).

# Taguette

Taguette is a web application written in Python. It is designed to run both on a desktop machine, in single-user mode, or on a server, where it allows real-time collaboration. In addition, we have been running a server at [app.taguette.org](https://app.taguette.org/) for anyone to use since March 2019, where we have about 2,000 monthly active users. Taguette is multiplatform, with installers provided for MacOS and Windows, a Docker image, and on the Python package Index (PyPI). It is available in 7 languages and has been downloaded over 12,000 times.

## Importing Documents

Work in Taguette begins with importing a document. We support a variety of text formats, including HTML, RTF, EPUB, PDF, DOCX, Markdown, and more. Documents are converted to HTML using the `ebook-convert` command, part of the Calibre ebook manager [@Calibre] or wvWare [@wvWare] for old Microsoft Word 97 `.doc` documents. A copy of Calibre is included in our installers so that users don't have to set up any additional software. After conversion, the document is sanitized to remove unwanted formatting and embedded media, and avoid security issues such as cross-site scripting.

## Analysis

After a user has imported a document into Taguette, they can then qualitatively highlight sections of text (see \autoref{fig:document}). Those highlights are organized in hierarchical tags that can be created, merged together, and recalled at will (see \autoref{fig:view-tag}). Data for all projects including documents, tags, and highlights is stored in a SQL database, which allows for easy exploration and scripting should the user need to go beyond the capabilities offered by our interface. In single-user mode, Taguette automatically creates a SQLite database in the user's home directory, and perform schema migrations automatically when a new version of Taguette is installed.

![Document view, where highlights are created and associated with tags.\label{fig:document}](01-document.png)

![List of highlights for a given tag.\label{fig:view-tag}](02-view-tag.png)

## Live collaboration

The multi-user version of Taguette allows for live collaboration of multiple users in a single project. It is possible to add other accounts as collaborators to your project, with a choice of permissions: some users can only tag, some can change documents, and others have full control including adding or removing collaborators.

![Adding collaborators through the interface.\label{fig:collabs}](03-collabs.png)

From then on, any change made by a different user is reflected immediately for the other users. This allows for faster annotation of large projects, without having to exchange partially processed documents via email for example. Taguette is currently the only free and open-source CAQDAS that supports this.

## Exporting

Taguette offers a variety of exporting options. A user can export a codebook as a document or spreadsheet, which is the list of all the tags, with their description and the number of associated highlights, throughout the project. Another option is to export a highlighted document, where the sections highlighted by the user are marked and each annotated with the associated tags. Finally, it is possible to export a list of all the highlights across documents, either for all tags or for a specific tag or hierarchy of tags (see \autoref{fig:export}).

![A highlighted document exported from Taguette and opened in LibreOffice.\label{fig:export}](04-export.png)

It is also possible to export a project as a SQLite3 database, in Taguette's native schema, which contains all the information necessary to continue work on another instance of Taguette. It is even possible to import them on our hosted version, [app.taguette.org](https://app.taguette.org/), or to export from there to a local copy. Older versions of the schema are automatically recognized and converted to the latest version if needed.

# Related Work

Other currently maintained open-source CAQDAS packages include: QualCoder [@qualcoder], qcoder [@qcoder], and qdap [@qdap]. qcoder and qdap are both R packages that support qualitative analysis of text, and require knowledge of R and RStudio to use. Both provide an interface to use the results of qualitative analysis with the rest of the R ecosystem. QualCoder is a desktop application (made with Python and PyQt5) that allows users to qualitatively analyze text and audiovisual materials. Each currently maintained tool fulfills different needs across the qualitative community, including Taguette. Previously maintained qualitative include Aquad [@AQUAD], RQDA [@RQDA], and the Coding Analysis Toolkit (CAT) [@CAT].

# Acknowledgments

We thank Dr. Sarah DeMott, whose work triggered the creation of Taguette. We would also like to thank our contributors on GitLab and our translators on Transifex, and the qualitative analysis community for their warm welcome and feedback.

In addition, we have recently started an [OpenCollective](https://opencollective.com/taguette) to support the development of Taguette, with the initial goal to cover the cost of a dedicated server for our hosted service. We are grateful to the backers for their kind donations to the project.

# References
