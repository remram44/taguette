FROM python:3.7 AS translations

RUN pip install babel==2.7.0 pytz==2019.3  # Keep in sync with poetry.lock

WORKDIR /usr/src/app
COPY po po
RUN mkdir scripts
COPY scripts/update_translations.sh scripts/

RUN scripts/update_translations.sh


FROM python:3.7

RUN apt-get update && \
    apt-get install -y --no-install-recommends calibre wv && \
    rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python && /root/.poetry/bin/poetry config virtualenvs.create false
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY taguette taguette
COPY pyproject.toml poetry.lock README.rst tests.py ./
RUN /root/.poetry/bin/poetry install --no-interaction --no-dev && rm -rf /root/.cache
COPY --from=translations /usr/src/app/taguette/l10n taguette/l10n

VOLUME /data
ENV HOME=/data
EXPOSE 7465
ENTRYPOINT ["taguette", "--no-browser", "--bind=0.0.0.0"]
CMD []
