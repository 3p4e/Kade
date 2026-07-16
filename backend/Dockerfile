FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System deps for PDF + OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgl1 \
        libglib2.0-0 \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Optional corporate-proxy CA bundle. Drop a PEM file at backend/extra-cas.crt
# (gitignored) and it gets appended to the system trust store. Without it,
# this is a no-op.
COPY extra-cas.cr[t] /tmp/extra-cas.crt
RUN if [ -s /tmp/extra-cas.crt ]; then \
      cp /tmp/extra-cas.crt /usr/local/share/ca-certificates/extra-cas.crt && \
      update-ca-certificates && \
      echo "Installed extra CAs"; \
    fi && rm -f /tmp/extra-cas.crt
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
