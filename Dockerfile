FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system --gid 10001 appuser \
    && useradd --system --uid 10001 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/logs /app/uploads \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8600

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c 'import urllib.error, urllib.request; status = 0; exec("try:\\n urllib.request.urlopen(\\"http://127.0.0.1:8600/api/me\\")\\nexcept urllib.error.HTTPError as error:\\n status = error.code"); raise SystemExit(status != 401)'

CMD ["uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8600"]
