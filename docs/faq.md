---
hide:
  - toc
---

# Frequently Asked Questions

## General info

### :material-account-voice: How do you pronounce Taguette?

It's pronounced like 'baguette' just with a 't' instead of a 'b' at the start! /tæˈɡɛt/

### :material-currency-usd-off: How much does it cost?

It's free!

Taguette costs nothing, either to use on your own machine or install on a server. It is published under an open license (BSD), which you can read here: [gitlab.com/remram44/taguette/blob/master/LICENSE.txt](https://gitlab.com/remram44/taguette/blob/master/LICENSE.txt).

If you would like to make a donation to Taguette, you can do so at our Open Collective: [opencollective.com/taguette](https://opencollective.com/taguette). Contributions will go towards maintenance work.

### :material-cloud-download-outline: Where can I install Taguette?

You can install Taguette on your own personal computer running macOS, Windows, or Linux — full instructions and download links can be found on our [installation guide](install.md). You can also install Taguette on a server if you need to collaborate with others — get a walkthrough on this process on our [self-host guide](self-host.md).

### :material-chair-school: How do I learn to use Taguette?

You could begin over at our [help guide](help-guide.md), which walks through all the current functionality of Taguette with screenshots. We also have a few presentations walkthroughs of Taguette's full capabilities that are hosted on the Open Science Framework here: [osf.io/xdszm/files](https://osf.io/xdszm/files/). Please make sure to look at the date for each presentation and pick the most recent one!

### :material-account-question-outline: Where can I get support for Taguette?

Feel free to shoot us an email over at [hi@taguette.org](mailto:hi@taguette.org) with your problem or question, and we will do our best to get back to you quickly — though please note we are not working on Taguette full-time, so give us a few days (though we will try to be as quick as possible!).

If you run into a bug or problem while using Taguette, or if you have a feature request, feel free to open an issue on GitLab, where Taguette's development takes place: [gitlab.com/remram44/taguette/-/issues](https://gitlab.com/remram44/taguette/-/issues) or email us with that as well if you are not comfortable with GitLab.

### :material-account-file-outline: Which file formats can I use with Taguette?

Taguette uses [Calibre](https://calibre-ebook.com/) to convert documents to HTML, so you can use all the formats it supports, including:

* Ebook formats (AZW, MOBI, EPUB)
* Microsoft Word (DOCX) 
* LibreOffice (ODT)
* PDF
* Plain text (TXT)
* HTML

See also Calibre's [FAQ entry](https://manual.calibre-ebook.com/faq.html#what-formats-does-calibre-support-conversion-to-from) on the subject.

### :material-book-heart-outline: I want to cite Taguette, how do I do that?

A mention is always appreciated! If you use Taguette for your research, please cite it with the following:

> Rampin et al., (2021). Taguette: open-source qualitative data analysis. Journal of Open Source Software, 6(68), 3522, https://doi.org/10.21105/joss.03522

If you need Bibtex, please use the following:

```
@article{Rampin2021,
  doi = {10.21105/joss.03522},
  url = {https://doi.org/10.21105/joss.03522},
  year = {2021},
  publisher = {The Open Journal},
  volume = {6},
  number = {68},
  pages = {3522},
  author = {Rémi Rampin and Vicky Rampin},
  title = {Taguette: open-source qualitative data analysis},
  journal = {Journal of Open Source Software}
```

## :material-account-lock-outline: Single-user info

### :material-account-star-outline: Why do you call the desktop versio of Taguette 'single user mode'?

Simply because you cannot collaborate with others using our desktop version of Taguette! If you want to be able to collaborate, see our [self-hosting guide](self-host.md) that walks you through how to install Taguette on a server for multi-user collaboration.

### :material-laptop: Does Taguette work on all operating systems?

Yes! You can install Taguette on macOS, Windows, and Linux.

### :material-folder-marker-outline: When I use Taguette on my personal computer, where is the data?

All your projects and documents are kept in a single database file. On macOS and Linux, you can find it at `~/.local/share/taguette/taguette.sqlite3`. On Windows, you can find it at: `My Documents/Taguette/taguette.sqlite3`.

### :material-database-sync-outline: SQLite is ok, but I prefer another database system. Can I change what Taguette uses?

Yes! On the terminal, use the --database option to change the location of your database or use a different database system. The argument is in the [format used by SQLAlchemy](https://docs.sqlalchemy.org/en/13/core/engines.html), so for instance:

* Unix or macOS: `sqlite:////home/myname/myfile.sqlite3`. Windows: `sqlite3:///C:\Users\myname\Documents\myfile.sqlite3`
* `postgresql://username:password@host:port/databasename`
* `mysql://user:password@host:port/databasename`
* Any of the other [backends supported by SQLAlchemy](https://docs.sqlalchemy.org/en/13/core/engines.html)

### :material-alert-outline: I installed Calibre, but importing documents shows 'Calibre is not available'

If you did not install Taguette from our Windows or macOS installers, you need to install Calibre separately.

Then, you need to make sure Calibre's `ebook-convert` program is either in your `PATH`, or in a directory you set as the `CALIBRE` environment variable.

For example, you can run Taguette like this: `CALIBRE=/path/to/calibre/bin taguette`

## :material-account-multiple-outline: Self-hosting/multi-user mode info

### :material-server-outline: Can I install Taguette on my own server?

Absolutely! We know that putting choice in the hands of our users is what open source is all about 😊 You can install Taguette on your server via Docker or right from the source. Both methods can be found with step-by-step instructions on our [self-hosting guide](self-host.md).

### :material-help-network-outline: I thought I followed the instructions but something went wrong -- what should I look at first?

Make sure you have correctly installed all the dependencies (via our self-hosting guide) and have also edited the configuration file. We have two sample configurations for you to work from as well: [nginx](https://gitlab.com/remram44/taguette/-/blob/master/contrib/nginx.conf) and [apache2](https://gitlab.com/remram44/taguette/-/blob/master/contrib/apache2.conf).

If you can't quite figure out what happened, either [submit an issue on GitLab](https://gitlab.com/remram44/taguette/issues), or email us at [hi@taguette.org](mailto:hi@taguette.org).

## :material-application-cog-outline: [app.taguette.org](https://app.taguette.org/) info

### :material-application-settings-outline: What is [app.taguette.org](https://app.taguette.org/)?

It is a version of Taguette hosted on our servers for free use by anyone! We host this from a rented dedicated server from [OVH](https://www.ovhcloud.com/en/bare-metal/), and our server's location is in France.

### :material-account-box-outline: What do we need to register for an account?

To use [app.taguette.org](https://app.taguette.org/), you need to register with a username and a password. You can provide an email address optionally, which we only use in case you forget your password.

### :material-folder-account-outline: What do you do with our account information?

We will only use it to log you into your account. We will never sell your information to anyone else.

### :material-file-document-alert-outline: What type of data should I upload to app.taguette.org?

TL;DR: do not upload sensitive data (e.g. patient information, student records).

A good reference for what data could be safely uploaded into [app.taguette.org](https://app.taguette.org/) is the U.S. Health and Human Services [Institutional Review Board exemption decision chart](https://www.hhs.gov/ohrp/regulations-and-policy/decision-charts/index.html#c2) -- if the data is exempt under this chart, it's most likely OK to upload to our hosted version of Taguette. If you're in a country outside the U.S., please refer to the ethics or human subject research boards of your country for exact information.

If you need to work collaboratively on sensitive data, then we would recommend reaching out to information technology at your organization and asking about a secure server in which they could install Taguette. If you are an independent researcher or do not have an IT unit at your institution that can do this for you, we would recommend procuring a secure server and installing Taguette there using our [self-hosting guide](self-host.md). Taguette can run well in many cloud hosting providers' free tiers (depending on the size of your data), and many of these providers have addendums to cover sensitive data (which may or may not incur a cost).

### :material-backup-restore: Do you back up the data on app.taguette.org?

Yes, we back up [app.taguette.org](https://app.taguette.org/) daily and keep those backups for a year. We send backups to a bucket in Amazon Web Services, in encrypted form only.