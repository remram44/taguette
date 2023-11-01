---
hide:
  - toc
---

# Self-hosting Taguette

Taguette can be run on a server, ideally for collaborative work. This is more difficult to set up, but then users can then use that installed version with nothing more than their web browser and work directly with their collaborators!

## Using Docker
If you so choose, you can simply run the Docker image hosted here: [quay.io/remram44/taguette](https://quay.io/repository/remram44/taguette). You will be prompted for an 'admin' password the first time. You can persist the data by mounting a volume over `/data`, like so:

```
docker run --rm quay.io/remram44/taguette default-config >/srv/taguette/config.py

# Edit configuration file, see section below on how
edit /srv/taguette/config.py

docker run -ti -p 80:7465 -v /srv/taguette:/data --restart=always quay.io/remram44/taguette server /data/config.py
```
If you want to use [docker-compose](https://docs.docker.com/compose/), you can replace the last command (after setting up the configuration file) by `docker-compose up`, with a `docker-compose.yml` like:

```
version: "2.4"
services:
  taguette:
    image: quay.io/remram44/taguette
    command: ["server", "/config.py"]
    ports: ["127.0.0.1:7465:7465"]
    volumes:
      - "./config.py:/config.py:ro"
      - "./data:/data"
```

## "Native" installation on a server

You need Python 3.5 or better to run Taguette. Simply run `pip install taguette` from the terminal to install the software. To be able to import non-HTML documents, you also need [Calibre](https://calibre.org) installed (specifically, the `ebook-convert` command).

Using a virtual environment is recommended. Example installation on Ubuntu:

```
apt update
apt install calibre python3.5 virtualenv
virtualenv --python=python3.5 /srv/taguette
. /srv/taguette/bin/activate
pip install taguette
taguette default-config >config.py
edit config.py
taguette --no-browser server config.py
```

### Configuration file

In either case, running the server requires a configuration file. This file contains important information, such as email server and addresses, the port number to listen on, which database to use, whether registration of new accounts is enabled, etc.

You can make Taguette print a configuration file for you to edit using: `taguette default-config`

You might want to change the `PORT` to `80`, or better yet configure a web-server to act as a proxy, see below.

To help with this, we provide example configuration files that you can use.

### Using a proxy server

For performance or security reasons, or simply because you want to host multiple sites on your machine, you might want to put a web-server (such as [nginx](https://nginx.org/) or [Apache](https://httpd.apache.org/)) in front of Taguette. That server will then simply relay connections to Taguette (a setup we call reverse proxy). You can use it to provide encryption using TLS (recommended) for example using [Let's Encrypt](https://letsencrypt.org/), free.

### Database

The `DATABASE` setting should be a SQLAlchemy connection string. For example, you can use:

* a SQLite database file (note the 4 slashes): `sqlite:////srv/taguette/taguette.sqlite3`
* a PostgreSQL database: `postgresql://user:secretpassword@localhost/taguette`
    * you need to `pip install psycopg2-binary`
* a MariaDB database ([MySQL currently doesn't work](https://gitlab.com/remram44/taguette/-/merge_requests/84)): `mysql+pymysql://user:secretpassword@localhost/taguette`
    * you need to `pip install pymysql cryptography`

... or any of the [other databases supported by SQLAlchemy](https://docs.sqlalchemy.org/en/13/core/engines.html). Note that we don't test on any other database, so you might run into issues.