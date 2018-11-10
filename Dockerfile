FROM python:3.6

RUN apt-get update && apt-get install -y calibre && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app
RUN pip install virtualenv && virtualenv /opt/venv
COPY taguette taguette
COPY setup.py README.rst tests.py Pipfile Pipfile.lock ./
RUN /opt/venv/bin/pip install pipenv && \
    . /opt/venv/bin/activate && pipenv install --deploy && \
    (echo "#!/bin/sh" && echo ". /opt/venv/bin/activate" && echo "exec taguette \"\$@\"") >/usr/local/bin/taguette && \
    chmod +x /usr/local/bin/taguette

VOLUME /data
ENV HOME=/data
EXPOSE 8000
ENTRYPOINT ["taguette", "--no-browser", "--bind=0.0.0.0"]
CMD ["--multiuser"]
