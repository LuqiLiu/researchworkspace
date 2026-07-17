FROM python:3.12-slim-bookworm@sha256:d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system django \
    && adduser --system --ingroup django --home /app django

COPY pyproject.toml requirements.lock README.md ./
COPY app ./app
COPY config ./config
COPY manage.py ./
RUN pip install --requirement requirements.lock \
    && pip install --no-build-isolation --no-deps .

COPY templates ./templates
COPY static ./static
COPY docker ./docker
RUN mkdir -p /app/var/static /app/var/media \
    && chmod +x /app/docker/entrypoint.sh \
    && chown -R django:django /app

USER django

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
