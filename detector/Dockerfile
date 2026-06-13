FROM python:3.12-slim

# copy uv binary only — no full uv install
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# dependencies first (cache layer)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# model artifacts
COPY ads_ml/config.yaml          ads_ml/config.yaml
COPY ads_ml/trained/             ads_ml/trained/

# inference code
COPY ads_ml/utils/               ads_ml/utils/
COPY detector.py                 .

ENV MODEL_DIR=/app/ads_ml \
    PYTHONUNBUFFERED=1

CMD ["python", "detector.py"]
