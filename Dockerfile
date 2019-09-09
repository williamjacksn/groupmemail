FROM python:3.7.4-alpine3.10

COPY requirements.txt /groupmemail/requirements.txt

RUN /sbin/apk add --no-cache --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk add --no-cache libpq \
 && /usr/local/bin/pip install --no-cache-dir --requirement /groupmemail/requirements.txt \
 && /sbin/apk del --no-cache .deps

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/groupmemail/run.py"]
HEALTHCHECK CMD ["/groupmemail/docker-healthcheck.sh"]

ENV PYTHONUNBUFFERED="1"

LABEL org.opencontainers.image.authors="William Jackson <william@subtlecoolness.com>" \
      org.opencontainers.image.version=3.0.1

COPY . /groupmemail
RUN chmod +x /groupmemail/docker-healthcheck.sh
