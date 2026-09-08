FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends librsvg2-bin ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY buybot ./buybot
COPY tools ./tools
COPY media ./media

RUN python tools/make_media.py \
    && useradd -r -u 10001 nox \
    && mkdir -p /app/state \
    && chown -R nox:nox /app/state

USER nox
ENV PYTHONUNBUFFERED=1 STATE_FILE=/app/state/state.json
VOLUME ["/app/state"]

CMD ["python", "-m", "buybot"]
