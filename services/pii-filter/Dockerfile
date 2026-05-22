FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

FROM base AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt
# spaCy Spanish model — baked into the image at build time, no runtime download.
RUN pip install --prefix=/install \
    https://github.com/explosion/spacy-models/releases/download/es_core_news_md-3.7.0/es_core_news_md-3.7.0-py3-none-any.whl

FROM base AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
# gRPC stubs (app/pii_pb2*.py) are committed; regenerate with grpcio-tools if the
# proto changes — see requirements-dev.txt.
COPY app ./app
COPY proto ./proto
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
EXPOSE 8002 50051
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
