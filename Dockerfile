FROM python:3.7.0-alpine3.8

COPY requirements-docker.txt /groupmemail/requirements-docker.txt

RUN /sbin/apk --no-cache add --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk --no-cache add libpq \
 && /usr/local/bin/pip install --no-cache-dir --requirement /groupmemail/requirements-docker.txt \
 && /sbin/apk del .deps

COPY . /groupmemail

ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/groupmemail/run.py"]

ENV PYTHONUNBUFFERED 1

LABEL maintainer=william@subtlecoolness.com \
      org.label-schema.schema-version=1.0 \
      org.label-schema.version=2.2.1
