FROM python:3.7.0-alpine3.8

COPY requirements.txt /app/requirements.txt

RUN /sbin/apk --no-cache add --virtual .deps gcc musl-dev postgresql-dev \
 && /sbin/apk --no-cache add libpq \
 && /usr/local/bin/pip install --no-cache-dir --upgrade pip setuptools \
 && /usr/local/bin/pip install --no-cache-dir --requirement /app/requirements.txt \
 && /sbin/apk del .deps

COPY . /app

EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/python"]
CMD ["/app/run.py"]
