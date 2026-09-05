FROM python:3.12-slim

ARG INSTALL_PROFILE=runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    THINKRAG_EMBED_PREWARM=0 \
    THINKRAG_OCR_PREWARM=0 \
    EMBEDDING_ALLOW_REMOTE_DOWNLOAD=0 \
    INSTALL_PROFILE=${INSTALL_PROFILE} \
    APP_RUNTIME_MODE=api

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt requirements-smoke.txt requirements.txt requirements-dev.txt requirements-eval.txt requirements-prod.txt ./

RUN python -m pip install --upgrade pip setuptools wheel \
    && case "$INSTALL_PROFILE" in \
        runtime) pip install -r requirements-runtime.txt ;; \
        smoke) pip install -r requirements-smoke.txt ;; \
        full) pip install -r requirements.txt ;; \
        dev) pip install -r requirements-dev.txt ;; \
        prod) pip install -r requirements-prod.txt ;; \
        eval) pip install -r requirements-eval.txt ;; \
        *) \
            echo "Unsupported INSTALL_PROFILE: $INSTALL_PROFILE" >&2; \
            exit 1; \
            ;; \
    esac

COPY . .

RUN sed -i 's/\r$//' /app/scripts/docker-entrypoint.sh \
    && chmod +x /app/scripts/docker-entrypoint.sh

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD []
