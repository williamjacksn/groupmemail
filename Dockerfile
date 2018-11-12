FROM python:3.7.1-alpine3.8

COPY requirements.txt /groupmemail/requirements.txt

RUN /sbin/apk add --no-cache --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk add --no-cache libpq \
 && /usr/local/bin/pip install --no-cache-dir --requirement /groupmemail/requirements.txt \
 && /sbin/apk del --no-cache .deps

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/groupmemail/run.py"]
HEALTHCHECK CMD ["/groupmemail/docker-healthcheck.sh"]

ENV PYTHONUNBUFFERED 1

LABEL maintainer=william@subtlecoolness.com \
      org.label-schema.schema-version=1.0 \
      org.label-schema.version=2.2.8

COPY . /groupmemail
RUN chmod +x /groupmemail/docker-healthcheck.sh
