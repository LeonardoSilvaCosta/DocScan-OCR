# syntax=docker/dockerfile:1
# Trixie fornece Ghostscript >= 10.03.0. As versoes 10.0.0 a 10.02.0
# podem corromper PDFs com texto existente quando --skip-text e usado.
FROM debian:trixie-slim

LABEL org.opencontainers.image.title="ScanLayer" \
      org.opencontainers.image.description="Camada OCR para PDFs escaneados com suporte a portugues"

ARG APP_UID=10001
ARG APP_GID=10001

# Dependencias de runtime fornecidas pelo Debian, sem ferramentas de compilacao.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3-venv \
        ca-certificates \
        tesseract-ocr \
        tesseract-ocr-por \
        tesseract-ocr-osd \
        ghostscript \
        unpaper \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml README.md /opt/scanlayer/
COPY src/ /opt/scanlayer/src/
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir /opt/scanlayer

RUN test "${APP_UID}" -gt 0 && test "${APP_GID}" -gt 0 \
    && groupadd --gid "${APP_GID}" appuser \
    && useradd --uid "${APP_UID}" --gid appuser --create-home \
        --shell /usr/sbin/nologin appuser \
    && install -d -m 0750 -o appuser -g appuser /data

ENV HOME=/home/appuser

WORKDIR /data
VOLUME ["/data"]
USER appuser:appuser

# Verificacoes executadas tambem como usuario non-root durante o build.
RUN ocrmypdf --version \
    && GHOSTSCRIPT_VERSION="$(gs --version)" \
    && dpkg --compare-versions "${GHOSTSCRIPT_VERSION}" ge 10.03.0 \
    && printf 'Ghostscript %s\n' "${GHOSTSCRIPT_VERSION}" \
    && unpaper --version \
    && tesseract --list-langs | grep -Fx por \
    && test "$(locale charmap)" = "UTF-8" \
    && test "$(id -u)" -ne 0 \
    && test -w /data

ENTRYPOINT ["scanlayer"]
CMD ["--help"]
