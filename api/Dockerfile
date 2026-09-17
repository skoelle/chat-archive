FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd -m -u 10001 apiuser \
    && chown -R apiuser:apiuser /app
USER apiuser

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/health')"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8420"]
