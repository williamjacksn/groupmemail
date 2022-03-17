FROM python:3.11.0a6-alpine3.15

COPY requirements.txt /groupmemail/requirements.txt

RUN /sbin/apk add --no-cache libpq
RUN /usr/local/bin/pip install --no-cache-dir --requirement /groupmemail/requirements.txt

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/groupmemail/run.py"]
HEALTHCHECK CMD ["/groupmemail/docker-healthcheck.sh"]

ENV APP_VERSION="2021.2" \
    PYTHONUNBUFFERED="1"

LABEL org.opencontainers.image.authors="William Jackson <william@subtlecoolness.com>" \
      org.opencontainers.image.version="${APP_VERSION}"

COPY . /groupmemail
RUN chmod +x /groupmemail/docker-healthcheck.sh
