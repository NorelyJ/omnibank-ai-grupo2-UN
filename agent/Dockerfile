FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema necesarias para compilar spaCy y curl para el HEALTHCHECK
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download es_core_news_sm

# Copiar el código
COPY . .

# Usuario no-root por seguridad (buena práctica DevOps)
RUN useradd --create-home --no-log-init appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
