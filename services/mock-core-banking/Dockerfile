FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

FROM base AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

FROM base AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app ./app
COPY data ./data
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
