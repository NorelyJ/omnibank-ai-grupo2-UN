FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

FROM base AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt
COPY proto ./proto
COPY app ./app
# Generate gRPC stubs into app/ and fix the relative import in the generated _grpc file.
RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    python -m grpc_tools.protoc -I=proto --python_out=app --grpc_python_out=app proto/pii.proto \
    && sed -i 's/^import pii_pb2/from . import pii_pb2/' app/pii_pb2_grpc.py

FROM base AS runtime
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --from=builder /build/app ./app
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
EXPOSE 8002 50051
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
