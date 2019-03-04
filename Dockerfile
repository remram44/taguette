FROM python:3.6

RUN apt-get update && \
    apt-get install -y calibre wv && \
    rm -rf /var/lib/apt/lists/*
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python && /root/.poetry/bin/poetry config settings.virtualenvs.create false
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
COPY taguette taguette
COPY pyproject.toml poetry.lock README.rst tests.py ./
RUN /root/.poetry/bin/poetry install --no-interaction && rm -rf /root/.cache

VOLUME /data
ENV HOME=/data
EXPOSE 8000
ENTRYPOINT ["taguette", "--no-browser", "--bind=0.0.0.0"]
CMD ["--multiuser"]
