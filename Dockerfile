FROM python:3.9 AS translations

RUN pip install babel==2.9.1 pytz==2021.3  # Keep in sync with poetry.lock

WORKDIR /usr/src/app
COPY po po
RUN mkdir scripts
COPY scripts/update_translations.sh scripts/

RUN scripts/update_translations.sh


FROM python:3.9

# Install Calibre from Ubuntu distro
RUN apt-get update && \
    apt-get install -y --no-install-recommends calibre wv && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python - --version 1.1.11 && /root/.poetry/bin/poetry config virtualenvs.create false

# Set up app
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY taguette taguette
COPY pyproject.toml poetry.lock README.rst tests.py ./
RUN /root/.poetry/bin/poetry install --no-interaction --no-dev && rm -rf /root/.cache

# Copy translation from other stage
COPY --from=translations /usr/src/app/taguette/l10n taguette/l10n

VOLUME /data
ENV HOME=/data
EXPOSE 7465
ENTRYPOINT ["taguette", "--no-browser", "--bind=0.0.0.0"]
CMD []
