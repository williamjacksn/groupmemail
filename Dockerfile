FROM python:3.13-slim

RUN /usr/sbin/useradd --create-home --shell /bin/bash --user-group python

USER python
RUN /usr/local/bin/python -m venv /home/python/venv

COPY --chown=python:python requirements.txt /home/python/groupmemail/requirements.txt
RUN /home/python/venv/bin/pip install --no-cache-dir --requirement /home/python/groupmemail/requirements.txt

ENTRYPOINT ["/home/python/venv/bin/python", "/home/python/groupmemail/run.py"]

ENV APP_VERSION="2024.1" \
    PATH="/home/python/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE="1" \
    PYTHONUNBUFFERED="1" \
    TZ="Etc/UTC"

LABEL org.opencontainers.image.authors="William Jackson <william@subtlecoolness.com>" \
      org.opencontainers.image.version="${APP_VERSION}"

COPY --chown=python:python run.py /home/python/groupmemail/run.py
COPY --chown=python:python groupmemail /home/python/groupmemail/groupmemail
